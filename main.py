#!/usr/bin/env python
# -*- coding: utf-8 -*-

from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch, memcache

import datetime
import re
import sys
import urllib
import xml.etree.ElementTree as etree
from ConfigParser import SafeConfigParser

import twoauth

from twilog import twilog

### 文字コード設定 ###
stdin = sys.stdin
stdout = sys.stdout
reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdin = stdin
sys.stdout = stdout
######################

"""
OAuth の各種キーを読み込む
"""
parser = SafeConfigParser()
parser.readfp(open('config.ini'))
sec = 'twitter'
consumer_key = parser.get(sec, 'consumer_key')
consumer_secret = parser.get(sec, 'consumer_secret')
access_token = parser.get(sec, 'access_token')
access_token_secret = parser.get(sec, 'access_token_secret')


api = twoauth.api(consumer_key,
                  consumer_secret,
                  access_token,
                  access_token_secret)

apiurl = 'http://markovchain-y.appspot.com/api/db'

def parse_tweet(text):
    reply = re.compile(u'@[\S]+')
    url = re.compile(r's?https?://[-_.!~*\'()a-zA-Z0-9;/?:@&=+$,%#]+', re.I)

    text = reply.sub('', text)
    text = url.sub('', text)
    text = text.replace(u'．', u'。')
    text = text.replace(u'，', u'、')
    text = text.replace(u'「', '')
    text = text.replace(u'」', '')
    text = text.replace(u'？', u'?')
    text = text.replace(u'！', u'!')
    return text


class Kana(db.Model):
    kana = db.StringProperty(required=True)
    name = db.StringProperty(required=True)


class Since(db.Model):
    id = db.IntegerProperty()


def get_tweet():
    tweetxml = urlfetch.fetch('%s/sentence' % (apiurl)).content
    dom = etree.fromstring(tweetxml)
    return dom.text


class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Hello world!')


class PostTweetHandler(webapp.RequestHandler):
    def get(self):
        tweet = get_tweet()
        api.status_update(tweet)


class ReplyTweetHandler(webapp.RequestHandler):
    def get(self):
        since_id = memcache.get('since_id')
        if since_id is None:
            since = Since.get_by_key_name('since_id')
            if since is not None:
                since_id = since.id

        mentions = api.mentions(since_id=since_id)

        reply_start = re.compile(u'(@.+?)\s', re.I | re.U)

        last_tweet = ''

        for status in mentions:
            screen_name = status['user']['screen_name']
            #to_text = reply_start.sub('', status['text'])

            #if isinstance(to_text, str):
            #    to_text = to_text.decode('utf-8')

            tweet = get_tweet()
            while tweet == last_tweet:
                tweet = get_tweet()
            last_tweet = tweet
            tweet = "@%s %s" %(screen_name, tweet)

            last_since_id = status['id']
            memcache.set('since_id', last_since_id)
            Since(key_name='since_id', id=int(last_since_id)).put()
            api.status_update(tweet, in_reply_to_status_id=last_since_id)


class LearnTweetHandler(webapp.RequestHandler):
    def get(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        log = twilog.Twilog()
        tweets = log.get_tweets('yono', yesterday)
        for tweet in tweets:
            text = parse_tweet(tweet)
            sentences = text.split(u'。')
            for sentence in sentences:
                postdata = {'sentences':sentence, 'user':'yono'}
                params = urllib.urlencode(postdata)
                urlfetch.fetch(url='%s/sentence' % (apiurl),
                               payload=params,
                               method=urlfetch.POST)


class SinceIdHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write(str(memcache.get('since_id')))


class LoadKanaHandler(webapp.RequestHandler):
    def post(self):
        kana, name = self.request.get('data').split('\t') 
        data = Kana(kana=kana, name=name)
        data.put()
        d = memcache.get(kana)
        if d is None:
            d = []
        d.append(name)
        memcache.set(kana, d)


def main():
    application = webapp.WSGIApplication(
            [('/', MainHandler),
            ('/tweet', PostTweetHandler),
            ('/reply', ReplyTweetHandler),
            ('/learn', LearnTweetHandler),
            ('/since_id', SinceIdHandler),
            ('/load_kana', LoadKanaHandler)],
    debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
