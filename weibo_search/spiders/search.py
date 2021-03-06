"""Crawl Weibo from the normally used weibo.com"""
import re
import scrapy
import weibo_search.utils.util as util
from weibo_search.items import WeiboSearchItem
from urllib.parse import unquote
from datetime import datetime, timedelta
from scrapy.utils.project import get_project_settings
from scrapy.exceptions import CloseSpider


class SearchSpider(scrapy.Spider):
    name = 'search'
    allowed_domains = ['weibo.com']
    settings = get_project_settings()
    keyword_list = settings.get('KEYWORD_LIST')
    weibo_type = util.convert_weibo_type(settings.get('WEIBO_TYPE'))
    contain_type = util.convert_contain_type(settings.get('CONTAIN_TYPE'))
    regions = util.get_regions(settings.get('REGION'))
    base_url = 'https://s.weibo.com'
    start_date = settings.get('START_DATE',
                              datetime.now().strftime('%Y-%m-%d'))
    end_date = settings.get('END_DATE', datetime.now().strftime('%Y-%m-%d'))

    def start_requests(self):

        start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.end_date,
                                     '%Y-%m-%d') + timedelta(days=1)
        start_str = start_date.strftime('%Y-%m-%d') + '-0'
        end_str = end_date.strftime('%Y-%m-%d') + '-0'
        for keyword in self.keyword_list:
            if not self.settings.get('REGION') or '全部' in self.settings.get(
                    'REGION'):
                base_url = 'https://s.weibo.com/weibo?q=%s' % keyword
                url = base_url + self.weibo_type
                url += self.contain_type
                url += '&timescope=custom:{}:{}'.format(start_str, end_str)
                print(url)
                yield scrapy.Request(url=url,
                                     callback=self.parse,
                                     meta={
                                         'base_url': base_url,
                                         'keyword': keyword
                                     })
            else:
                for region in self.regions.values():
                    base_url = (
                        'https://s.weibo.com/weibo?q={}&region=custom:{}:1000'
                    ).format(keyword, region['code'])
                    url = base_url + self.weibo_type
                    url += self.contain_type
                    url += '&timescope=custom:{}:{}'.format(start_str, end_str)
                    # 获取一个省的搜索结果
                    yield scrapy.Request(url=url,
                                         callback=self.parse,
                                         meta={
                                             'base_url': base_url,
                                             'keyword': keyword,
                                             'province': region
                                         })

    def parse(self, response):
        """
        parse weibo web page,
        :param response:
        :return:
        """
        print('start parse')
        base_url = response.meta.get('base_url')
        keyword = response.meta.get('keyword')
        province = response.meta.get('province')
        print(base_url, keyword, province)
        is_empty = response.xpath(
            '//div[@class="card card-no-result s-pt20b40"]')
        page_count = len(response.xpath('//ul[@class="s-scroll"]/li'))
        print(is_empty, page_count)
        if is_empty:
            print('No Search Results!')
        elif page_count < 50:
            """if page count less than 50, just parse"""
            # 解析当前页面
            print('<50')
            for weibo in self.parse_weibo(response):
                # self.check_environment()
                yield weibo
            next_url = response.xpath(
                '//a[@class="next"]/@href').extract_first()
            if next_url:
                next_url = self.base_url + next_url
                yield scrapy.Request(url=next_url,
                                     callback=self.parse_page,
                                     meta={'keyword': keyword})
        else:
            " If over 50 page for one search, search day by day"
            print('by day')
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(self.end_date, '%Y-%m-%d')
            while start_date <= end_date:
                start_str = start_date.strftime('%Y-%m-%d') + '-0'
                start_date = start_date + timedelta(days=1)
                end_str = start_date.strftime('%Y-%m-%d') + '-0'
                url = base_url + self.weibo_type
                url += self.contain_type
                url += '&timescope=custom:{}:{}&page=1'.format(
                    start_str, end_str)
                "Get one day results "
                yield scrapy.Request(url=url,
                                     callback=self.parse_by_day,
                                     meta={
                                         'base_url': base_url,
                                         'keyword': keyword,
                                         'province': province,
                                         'date': start_str[:-2]
                                     })

    def parse_by_day(self, response):
        """Search by Day"""
        base_url = response.meta.get('base_url')
        keyword = response.meta.get('keyword')
        province = response.meta.get('province')
        is_empty = response.xpath(
            '//div[@class="card card-no-result s-pt20b40"]')
        date = response.meta.get('date')
        page_count = len(response.xpath('//ul[@class="s-scroll"]/li'))
        if is_empty:
            print('No Search Results!')
        elif page_count < 50:
            # 解析当前页面
            for weibo in self.parse_weibo(response):
                # self.check_environment()
                yield weibo
            next_url = response.xpath(
                '//a[@class="next"]/@href').extract_first()
            if next_url:
                next_url = self.base_url + next_url
                yield scrapy.Request(url=next_url,
                                     callback=self.parse_page,
                                     meta={'keyword': keyword})
        else:
            print('by hour')
            start_date_str = date + '-0'
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d-%H')
            for i in range(1, 25):
                start_str = start_date.strftime('%Y-%m-%d-X%H').replace(
                    'X0', 'X').replace('X', '')
                start_date = start_date + timedelta(hours=1)
                end_str = start_date.strftime('%Y-%m-%d-X%H').replace(
                    'X0', 'X').replace('X', '')
                url = base_url + self.weibo_type
                url += self.contain_type
                url += '&timescope=custom:{}:{}&page=1'.format(
                    start_str, end_str)
                "Search one hour results"
                yield scrapy.Request(url=url,
                                     callback=self.parse_by_hour_province
                                     if province else self.parse_by_hour,
                                     meta={
                                         'base_url': base_url,
                                         'keyword': keyword,
                                         'province': province,
                                         'start_time': start_str,
                                         'end_time': end_str
                                     })

    def parse_by_hour(self, response):
        """Search by hour"""
        keyword = response.meta.get('keyword')
        is_empty = response.xpath(
            '//div[@class="card card-no-result s-pt20b40"]')
        start_time = response.meta.get('start_time')
        end_time = response.meta.get('end_time')
        page_count = len(response.xpath('//ul[@class="s-scroll"]/li'))
        if is_empty:
            print('No Search Results!')
        elif page_count < 50:
            # 解析当前页面
            for weibo in self.parse_weibo(response):
                # self.check_environment()
                yield weibo
            next_url = response.xpath(
                '//a[@class="next"]/@href').extract_first()
            if next_url:
                next_url = self.base_url + next_url
                yield scrapy.Request(url=next_url,
                                     callback=self.parse_page,
                                     meta={'keyword': keyword})
        else:
            print('by hour and location 1000个')
            for region in self.regions.values():
                url = ('https://s.weibo.com/weibo?q={}&region=custom:{}:1000'
                       ).format(keyword, region['code'])
                url += self.weibo_type
                url += self.contain_type
                url += '&timescope=custom:{}:{}&page=1'.format(
                    start_time, end_time)
                "Search by one hour and one province"
                yield scrapy.Request(url=url,
                                     callback=self.parse_by_hour_province,
                                     meta={
                                         'keyword': keyword,
                                         'start_time': start_time,
                                         'end_time': end_time,
                                         'province': region
                                     })

    def parse_by_hour_province(self, response):
        """Search by hour, city/province"""
        keyword = response.meta.get('keyword')
        is_empty = response.xpath(
            '//div[@class="card card-no-result s-pt20b40"]')
        start_time = response.meta.get('start_time')
        end_time = response.meta.get('end_time')
        province = response.meta.get('province')
        page_count = len(response.xpath('//ul[@class="s-scroll"]/li'))
        if is_empty:
            print('No Search Results!')
        elif page_count < 50:
            # 解析当前页面
            for weibo in self.parse_weibo(response):
                # self.check_environment()
                yield weibo
            next_url = response.xpath(
                '//a[@class="next"]/@href').extract_first()
            if next_url:
                next_url = self.base_url + next_url
                yield scrapy.Request(url=next_url,
                                     callback=self.parse_page,
                                     meta={'keyword': keyword})
        else:
            for city in province['city'].values():
                url = ('https://s.weibo.com/weibo?q={}&region=custom:{}:{}'
                       ).format(keyword, province['code'], city)
                url += self.weibo_type
                url += self.contain_type
                url += '&timescope=custom:{}:{}&page=1'.format(
                    start_time, end_time)
                # 获取一小时一个城市的搜索结果
                yield scrapy.Request(url=url,
                                     callback=self.parse_page,
                                     meta={
                                         'keyword': keyword,
                                         'start_time': start_time,
                                         'end_time': end_time,
                                         'province': province,
                                         'city': city
                                     })

    def parse_page(self, response):
        """Parse information for one page search"""
        keyword = response.meta.get('keyword')
        is_empty = response.xpath(
            '//div[@class="card card-no-result s-pt20b40"]')
        if is_empty:
            print('No Search Results!')
        else:
            for weibo in self.parse_weibo(response):
                yield weibo
            next_url = response.xpath(
                '//a[@class="next"]/@href').extract_first()
            if next_url:
                next_url = self.base_url + next_url
                yield scrapy.Request(url=next_url,
                                     callback=self.parse_page,
                                     meta={'keyword': keyword})

    def get_article_url(self, selector):
        """Get passage link"""
        article_url = ''
        text = selector.xpath('string(.)').extract_first().replace(
            '\u200b', '').replace('\ue627', '').replace('\n',
                                                        '').replace(' ', '')
        if text.startswith('发布了头条文章'):
            urls = selector.xpath('.//a')
            for url in urls:
                if url.xpath(
                        'i[@class="wbicon"]/text()').extract_first() == 'O':
                    if url.xpath('@href').extract_first() and url.xpath(
                            '@href').extract_first().startswith('http://t.cn'):
                        article_url = url.xpath('@href').extract_first()
                    break
        return article_url

    def get_location(self, selector):
        """Get the publication location"""
        a_list = selector.xpath('.//a')
        location = ''
        for a in a_list:
            if a.xpath('./i[@class="wbicon"]') and a.xpath(
                    './i[@class="wbicon"]/text()').extract_first() == '2':
                location = a.xpath('string(.)').extract_first()[1:]
                break
        return location

    def get_at_users(self, selector):
        """Get the @ Name in weibo"""
        a_list = selector.xpath('.//a')
        at_users = ''
        at_list = []
        for a in a_list:
            if len(unquote(a.xpath('@href').extract_first())) > 14 and len(
                    a.xpath('string(.)').extract_first()) > 1:
                if unquote(a.xpath('@href').extract_first())[14:] == a.xpath(
                        'string(.)').extract_first()[1:]:
                    at_user = a.xpath('string(.)').extract_first()[1:]
                    if at_user not in at_list:
                        at_list.append(at_user)
        if at_list:
            at_users = ','.join(at_list)
        return at_users

    def get_topics(self, selector):
        """Get topics for one weibo"""
        a_list = selector.xpath('.//a')
        topics = ''
        topic_list = []
        for a in a_list:
            text = a.xpath('string(.)').extract_first()
            if len(text) > 2 and text[0] == '#' and text[-1] == '#':
                if text[1:-1] not in topic_list:
                    topic_list.append(text[1:-1])
        if topic_list:
            topics = ','.join(topic_list)
        return topics

    def parse_weibo(self, response):
        """Parse one mblog"""
        keyword = response.meta.get('keyword')
        for sel in response.xpath("//div[@class='card-wrap']"):
            info = sel.xpath(
                "div[@class='card']/div[@class='card-feed']/div[@class='content']/div[@class='info']"
            )
            if info:
                weibo = WeiboSearchItem()
                weibo['id'] = sel.xpath('@mid').extract_first()
                weibo['bid'] = sel.xpath(
                    '(.//p[@class="from"])[last()]/a[1]/@href').extract_first(
                    ).split('/')[-1].split('?')[0]
                weibo['user_id'] = info[0].xpath(
                    'div[2]/a/@href').extract_first().split('?')[0].split(
                        '/')[-1]
                weibo['screen_name'] = info[0].xpath(
                    'div[2]/a/@nick-name').extract_first()
                txt_sel = sel.xpath('.//p[@class="txt"]')[0]
                retweet_sel = sel.xpath('.//div[@class="card-comment"]')
                retweet_txt_sel = ''
                if retweet_sel and retweet_sel[0].xpath('.//p[@class="txt"]'):
                    retweet_txt_sel = retweet_sel[0].xpath('.//p[@class="txt"]')[0]
                content_full = sel.xpath('.//p[@node-type="feed_list_content_full"]')
                "deal with origin weibo and retweets"
                is_long_weibo = False
                is_long_retweet = False
                if content_full:
                    if not retweet_sel:
                        txt_sel = content_full[0]
                        is_long_weibo = True
                    elif len(content_full) == 2:
                        txt_sel = content_full[0]
                        retweet_txt_sel = content_full[1]
                        is_long_weibo = True
                        is_long_retweet = True
                    elif retweet_sel[0].xpath('.//p[@node-type="feed_list_content_full"]'):
                        retweet_txt_sel = retweet_sel[0].xpath('.//p[@node-type="feed_list_content_full"]')[0]
                        is_long_retweet = True
                    else:
                        txt_sel = content_full[0]
                        is_long_weibo = True
                weibo['text'] = txt_sel.xpath('string(.)').extract_first().replace('\u200b', '').replace(
                        '\ue627', '')
                weibo['article_url'] = self.get_article_url(txt_sel)
                weibo['location'] = self.get_location(txt_sel)
                if weibo['location']:
                    weibo['text'] = weibo['text'].replace('2' + weibo['location'], '')
                weibo['text'] = weibo['text'][2:].replace(' ', '')
                if is_long_weibo:
                    weibo['text'] = weibo['text'][:-6]
                weibo['at_users'] = self.get_at_users(txt_sel)
                weibo['topics'] = self.get_topics(txt_sel)
                reposts_count = sel.xpath('.//a[@action-type="feed_list_forward"]/text()').extract_first()
                try:
                    reposts_count = re.findall(r'\d+.*', reposts_count)
                except TypeError:
                    print('cookie无效或已过期')
                    raise CloseSpider()
                weibo['reposts_count'] = reposts_count[0] if reposts_count else '0'
                comments_count = sel.xpath('.//a[@action-type="feed_list_comment"]/text()').extract_first()
                comments_count = re.findall(r'\d+.*', comments_count)
                weibo['comments_count'] = comments_count[
                    0] if comments_count else '0'
                attitudes_count = sel.xpath('(.//a[@action-type="feed_list_like"])[last()]/em/text()').extract_first()
                weibo['attitudes_count'] = (attitudes_count if attitudes_count else '0')
                created_at = sel.xpath('(.//p[@class="from"])[last()]/a[1]/text()').extract_first(
                    ).replace(' ', '').replace('\n', '').split('前')[0]
                weibo['created_at'] = util.standardize_date(created_at)
                source = sel.xpath('(.//p[@class="from"])[last()]/a[2]/text()').extract_first()
                weibo['source'] = source if source else ''
                pics = ''
                is_exist_pic = sel.xpath('.//div[@class="media media-piclist"]')
                if is_exist_pic:
                    pics = is_exist_pic[0].xpath('ul[1]/li/img/@src').extract()
                    pics = [pic[2:] for pic in pics]
                    pics = [re.sub(r'/.*?/', '/large/', pic, 1) for pic in pics]
                    pics = ['http://' + pic for pic in pics]
                video_url = ''
                is_exist_video = sel.xpath('.//div[@class="thumbnail"]/a/@action-data')
                if is_exist_video:
                    video_url = is_exist_video.extract_first()
                    video_url = unquote(
                        str(video_url)).split('video_src=//')[-1]
                    video_url = 'http://' + video_url
                ""
                if not retweet_sel:
                    weibo['pics'] = pics
                    weibo['video_url'] = video_url
                else:
                    weibo['pics'] = ''
                    weibo['video_url'] = ''
                weibo['retweet_id'] = ''
                if retweet_sel and retweet_sel[0].xpath('.//div[@node-type="feed_list_forwardContent"]/a[1]'):
                    retweet = WeiboSearchItem()
                    retweet['id'] = retweet_sel[0].xpath('.//a[@action-type="feed_list_like"]/@action-data'
                                                         ).extract_first()[4:]
                    retweet['bid'] = retweet_sel[0].xpath('.//p[@class="from"]/a/@href').extract_first().split(
                        '/')[-1].split('?')[0]
                    info = retweet_sel[0].xpath('.//div[@node-type="feed_list_forwardContent"]/a[1]')[0]
                    retweet['user_id'] = info.xpath('@href').extract_first().split('/')[-1]
                    retweet['screen_name'] = info.xpath('@nick-name').extract_first()
                    retweet['text'] = retweet_txt_sel.xpath('string(.)').extract_first().replace(
                        '\u200b', '').replace('\ue627', '')
                    retweet['article_url'] = self.get_article_url(
                        retweet_txt_sel)
                    retweet['location'] = self.get_location(retweet_txt_sel)
                    if retweet['location']:
                        retweet['text'] = retweet['text'].replace('2' + retweet['location'], '')
                    retweet['text'] = retweet['text'][2:].replace(' ', '')
                    if is_long_retweet:
                        retweet['text'] = retweet['text'][:-6]
                    retweet['at_users'] = self.get_at_users(retweet_txt_sel)
                    retweet['topics'] = self.get_topics(retweet_txt_sel)
                    reposts_count = retweet_sel[0].xpath('.//ul[@class="act s-fr"]/li/a[1]/text()').extract_first()
                    reposts_count = re.findall(r'\d+.*', reposts_count)
                    retweet['reposts_count'] = reposts_count[0] if reposts_count else '0'
                    comments_count = retweet_sel[0].xpath('.//ul[@class="act s-fr"]/li[2]/a[1]/text()').extract_first()
                    comments_count = re.findall(r'\d+.*', comments_count)
                    retweet['comments_count'] = comments_count[0] if comments_count else '0'
                    attitudes_count = retweet_sel[0].xpath('.//a[@action-type="feed_list_like"]/em/text()').extract_first()
                    retweet['attitudes_count'] = (attitudes_count if attitudes_count else '0')
                    created_at = retweet_sel[0].xpath('.//p[@class="from"]/a[1]/text()').extract_first(
                        ).replace(' ', '').replace('\n', '').split('前')[0]
                    retweet['created_at'] = util.standardize_date(created_at)
                    source = retweet_sel[0].xpath('.//p[@class="from"]/a[2]/text()').extract_first()
                    retweet['source'] = source if source else ''
                    retweet['pics'] = pics
                    retweet['video_url'] = video_url
                    retweet['retweet_id'] = ''
                    yield {'weibo': retweet, 'keyword': keyword}
                    weibo['retweet_id'] = retweet['id']
                print(weibo['created_at'])
                yield {'weibo': weibo, 'keyword': keyword}

