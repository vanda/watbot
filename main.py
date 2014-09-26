#!/usr/bin/env python
import ConfigParser
from datetime import datetime, timedelta
import json
import os
import urllib2
import webapp2
import jinja2
import tweepy
import logging
from google.appengine.api import memcache
from memcache_decorator import cached
from roomlookup import ROOMLOOKUPDICT

WORKSHOP = 15
SPECIAL_EVENT = 24
EVENING_TALK_CODE = 40
DAILY_TOUR_CODE = 41
BSL_TALK = 42
SEMINAR = 44
MEMBERSHIP_EVENT_CODE = 45

TWEET_MEMCACHE_TTL = 60*60*24*7

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


def days_delta(n):
    return timedelta(days=n)



def get_first_int_in_list(src_list):
    for i in src_list:
        try:
            return(int(i))
        except ValueError:
            pass
            
def send_tweet(msg,debug=False):
    config = ConfigParser.RawConfigParser()
    config.read('settings.cfg')
    CONSUMER_KEY = config.get('Twitter OAuth', 'CONSUMER_KEY')
    CONSUMER_SECRET = config.get('Twitter OAuth', 'CONSUMER_SECRET')
    ACCESS_TOKEN_KEY = config.get('Twitter OAuth', 'ACCESS_TOKEN_KEY')
    ACCESS_TOKEN_SECRET = config.get('Twitter OAuth', 'ACCESS_TOKEN_SECRET')
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    if debug:
        logging.info(msg)
        result = 'logged: %s' % msg
    else:
        result = api.update_status(msg)
    return result

def add_ordinal(day):
    if day[-1] == '1':
        return '%sst' % day
    elif day[-1] == '2':
        return '%snd' % day
    elif day[-1] == '3':
        return '%srd' % day
    return '%sth' % day

def strip_leading_zero(day):
    return day.lstrip('0')

def craft_tweet(event):
    event_datetime = datetime.strptime(event['fields']['last_slot'], '%Y-%m-%d %H:%M:%S')
    display_day = add_ordinal(strip_leading_zero(event_datetime.strftime('%d')))
    display_month = event_datetime.strftime('%b')
    display_time = event_datetime.strftime('%H:%M')
    display_url = 'http://www.vam.ac.uk/whatson/event/%s' % event['pk']
    if event_datetime.date() == datetime.today().date():
        display_datetime = 'Today at %s' % display_time
    else:
        display_datetime = '%s %s %s' % (display_day, display_month, display_time)
    tweet = '%s: %s | %s' % (display_datetime, event['fields']['name'].encode('utf8'), display_url)
    return tweet

def get_events_on_date(scandate):
    urlpath = "http://www.vam.ac.uk/whatson/json/events/day/%s/" % scandate
    response = urllib2.urlopen(urlpath)
    data = json.load(response)
    return data

def filter_irrelevant_events(events):
    relevant = []
    for d in events:
        if d['fields']['event_type'] in [WORKSHOP, SPECIAL_EVENT, EVENING_TALK_CODE, BSL_TALK, SEMINAR, MEMBERSHIP_EVENT_CODE]:
            relevant.append(d)
    return relevant

def prioritise_relevant_events(events):
    for i, d in enumerate(events):
        if 'Friday Late' in d['fields']['name']:
            events.insert(0, events.pop(i))
    return events



class ImportHandler(webapp2.RequestHandler):

    def cache_daily_event(self, import_date):
        value = memcache.get(import_date)
        if not value:
            events = get_events_on_date(import_date)
            events = filter_irrelevant_events(events)
            events = prioritise_relevant_events(events)
            try:
                event = events[0]
            except IndexError:
                pass
            else:
                memcache.set(import_date, event, time=TWEET_MEMCACHE_TTL)
                return event

    def get(self):
        for daycount in range(0,6):
            scandate = (datetime.now() + days_delta(daycount)).strftime("%Y%m%d")
            self.cache_daily_event(scandate)
        self.response.write('<hr>')


class HomeHandler(webapp2.RequestHandler):
    def get(self):
        template = jinja_environment.get_template('templates/main.html')
        self.response.out.write(template.render({}))


app = webapp2.WSGIApplication([
    ('/import', ImportHandler),
    ('.*', HomeHandler)
], debug=True)
