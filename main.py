#!/usr/bin/env python
import ConfigParser
from datetime import datetime, timedelta
import json
import os
import urllib2
import webapp2
import jinja2
import pytz
import tweepy
import bitly_api
import logging
from memcache_decorator import cached
from google.appengine.api import memcache
from random import choice
from roomlookup import ROOMLOOKUPDICT
from vector import Document

DAYS_TO_GET = 7

YOUNG_PEOPLES_EVENT = 10
WORKSHOP = 15
SPECIAL_EVENT = 24
EVENING_TALK_CODE = 40
DAILY_TOUR_CODE = 41
BSL_TALK = 42
SEMINAR = 44
MEMBERSHIP_EVENT_CODE = 45

ELLIPSIS = '...'
HASHTAG_COUNT = 1
TWITTER_CHAR_LIMIT = 140
TWEET_MEMCACHE_TTL = 60*60*24*7 # a week
BITLY_CACHE_TTL = 60*60*24*32  # a month
ELLIPSIS = '...'
config = ConfigParser.RawConfigParser()
config.read('settings.cfg')
CONSUMER_KEY = config.get('Twitter OAuth', 'CONSUMER_KEY')
CONSUMER_SECRET = config.get('Twitter OAuth', 'CONSUMER_SECRET')
ACCESS_TOKEN_KEY = config.get('Twitter OAuth', 'ACCESS_TOKEN_KEY')
ACCESS_TOKEN_SECRET = config.get('Twitter OAuth', 'ACCESS_TOKEN_SECRET')
BITLY_ACCESS_TOKEN = config.get('Bitly', 'BITLY_ACCESS_TOKEN')
DEBUG = config.get('debug', 'DEBUG') == "True"
LOCAL_TZ = pytz.timezone('Europe/London')

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


def days_delta(n):
    return timedelta(days=n)


def format_date_from_memcache(days_ahead=0):
    """
    :param days_ahead:0-7
    :return:20141030
    """
    return (datetime.now(tz=LOCAL_TZ) + days_delta(days_ahead)).strftime("%Y%m%d")


def get_first_int_in_list(src_list):
    for i in src_list:
        try:
            return(int(i))
        except ValueError:
            pass

def extract_keywords(doc, keyword_count=5):
    d = Document(doc)
    results = d.keywords(top=keyword_count)
    # results = [(round(i,2),j) for (i,j) in results]
    results = [j for (i,j) in results]
    return results


def send_tweet(msg, debug=False):
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    if debug:
        logging.info('[DEBUG] Sending tweet: %s' % msg)
        result = 'logged: %s' % msg
    else:
        try:
            result = api.update_status(msg)
        except tweepy.TweepError as e:
            logging.info('Send tweet failed: %s' % e.message[0]['message'])
            return False
        else:
            return result


def add_ordinal(day):
    day = str(day)
    day_last_character = day[-1]
    lookup = {"1": "%sst", "2": "%snd", "3": "%srd"}

    try:
        return lookup[day_last_character] % day
    except KeyError:
        return '%sth' % day


def strip_leading_zero(day):
    return day.lstrip('0')

def process_event(event):
    event_datetime = datetime.strptime(event['event_dt'], '%Y-%m-%d %H:%M:%S')
    display_day = add_ordinal(strip_leading_zero(event_datetime.strftime('%d')))
    display_month = event_datetime.strftime('%b')
    display_time = event_datetime.strftime('%H:%M')
    display_url = 'http://www.vam.ac.uk/whatson/event/%s' % event['pk']
    display_url = craft_bitlylink(display_url)
    hashtag = event.get('keywords',[])
    logging.info('hashtag')
    logging.info(hashtag)

    return display_day, display_month, display_time, display_url, event_datetime, hashtag

def craft_just_starting_tweet(event):
    display_day, display_month, display_time, display_url, event_datetime, hashtag = process_event(event)
    event_title = event['fields']['name'].encode('utf8')
    display_datetime = 'Just about to start'
    tweet = construct_tweet(display_datetime, display_url, event_title, hashtag)
    return tweet

def craft_today_tweet(event):
    display_day, display_month, display_time, display_url, event_datetime, hashtag = process_event(event)
    display_datetime = 'Today at %s' % display_time
    event_title = event['fields']['name'].encode('utf8')
    tweet = construct_tweet(display_datetime, display_url, event_title, hashtag)
    return tweet

def make_tweet_string(display_datetime, display_url, event_title, hashtag):
    for tag in hashtag[:]:
        if tag in event_title.lower():
            tagloc = event_title.lower().find(tag)
            event_title = event_title[:tagloc] + '#' + event_title[tagloc:]
            hashtag.remove(tag)
    if hashtag:
        hashtag = ' '.join(['#%s'% k for k in hashtag][:HASHTAG_COUNT])
        hashtag = ',' + hashtag
    else:
        hashtag = ''
    # if title much shorter than hashtag list, omit the tags
    if len(event_title) < len(hashtag)*2:
        hashtag = ''
    tweet = '%s: %s%s | %s' % (display_datetime, event_title, hashtag, display_url)
    return tweet


def construct_tweet(display_datetime, display_url, event_title, hashtag=''):
    tweet = make_tweet_string(display_datetime, display_url, event_title, hashtag)
    if len(tweet) > TWITTER_CHAR_LIMIT:
        MINIMAL_TWEET_PATTERN = '%s: %s | %s'
        mandatory_chars_len = len(MINIMAL_TWEET_PATTERN % (display_datetime, ELLIPSIS.encode('utf8'), display_url))
        event_title = '%s%s' % (event_title[:TWITTER_CHAR_LIMIT - mandatory_chars_len],ELLIPSIS)
        tweet = MINIMAL_TWEET_PATTERN % (display_datetime, event_title, display_url)
    return tweet


def craft_upcoming_tweet(event):
    display_day, display_month, display_time, display_url, event_datetime, hashtag = process_event(event)
    display_datetime = '%s %s %s' % (display_day, display_month, display_time)
    event_title = event['fields']['name'].encode('utf8')
    tweet = construct_tweet(display_datetime, display_url, event_title, hashtag)
    return tweet


def craft_tweet(event):
    display_day, display_month, display_time, display_url, event_datetime, hashtag = process_event(event)
    if event_datetime.date() == datetime.today().date():
        tweet = craft_today_tweet(event)
    else:
        tweet = craft_upcoming_tweet(event)
    return tweet


def get_events_on_date(scandate):
    urlpath = "http://www.vam.ac.uk/whatson/json/events/day/%s/" % scandate

    try:
        response = urllib2.urlopen(urlpath)
    except urllib2.HTTPError:
        logging.info('Unable to get events for %s' % scandate)
        return []
    else:
        data = json.load(response)
        return data


def check_for_matching_dates(event, current_date):
    '''
    Returns True if dates match.
    '''
    event_date = datetime.strptime(event['fields']['first_slot'], '%Y-%m-%d %H:%M:%S')
    if event_date.date() == current_date.date():
        return True
    return False


def check_for_relevant_event(event):
    '''
    Returns True if event is 'interesting'
    '''
    if event['fields']['event_type'] in [YOUNG_PEOPLES_EVENT, WORKSHOP, SPECIAL_EVENT, EVENING_TALK_CODE, BSL_TALK, SEMINAR, MEMBERSHIP_EVENT_CODE]:
        return True
    return False

def filter_events(events, current_date):
    current_date = datetime.strptime(current_date, '%Y%m%d')

    filtered_events = []
    for event in events:
        relevant = check_for_relevant_event(event)
        if relevant:
            filtered_events.append(event)

    return filtered_events


def add_event_date(event, occurance_date):
    occurance_date = datetime.strptime(occurance_date, '%Y%m%d')
    event_date = datetime.strptime(event['fields']['first_slot'], '%Y-%m-%d %H:%M:%S')
    event_date = datetime(occurance_date.year, occurance_date.month, occurance_date.day, event_date.hour, event_date.minute)
    event['event_dt'] = str(event_date)
    return event


def add_priority_to_events(events):
    for i, d in enumerate(events):
        d['priority'] = 0
        # We pretty much always want to see Friday Lates
        if 'friday late' in d['fields']['name'].lower():
            d['priority'] += 100
        # If start date is today then probably a one off or opening day
        current_time = datetime.now(tz=LOCAL_TZ)
        if check_for_matching_dates(d, current_time):
            d['priority'] += 10
        # You encourage young people. Collect 10
        if d['fields']['event_type'] == YOUNG_PEOPLES_EVENT:
            d['priority'] += 10
        # Lunchtime talk. Collect 10
        if 'lunchtime' in d['fields']['short_description'].lower():
            d['priority'] += 10
        # Workshop. Collect 10
        if 'workshop' in d['fields']['short_description'].lower():
            d['priority'] += 10

        # Curator mentioned. Collect 10
        if 'curator' in d['fields']['long_description'].lower():
            d['priority'] += 10

        # Membership events are allowed, but it isn't ideal
        if d['fields']['event_type'] == MEMBERSHIP_EVENT_CODE:
            d['priority'] -= 50
        # We never want to show sold out events. Go directly to jail.  Do not pass Go. Do not collect 200
        if 'sold out' in d['fields']['event_note']:
            d['priority'] -= 100
    return events

def add_keywords(events):
    for event in events:
        event_text = '%s %s %s %s' % (
            event['fields']['name'],
            event['fields']['long_description'],
            event['fields']['short_description'],
            event['fields']['free_tag']
        )
        event['keywords'] = extract_keywords(event_text)
    return events


def sort_events_by_priority(events):
    events = sorted(events, key=lambda k: k['priority'])
    events.reverse()
    return events


@cached(time=BITLY_CACHE_TTL)
def craft_bitlylink(url):
    bitly = bitly_api.Connection(access_token=BITLY_ACCESS_TOKEN)
    data = bitly.shorten(url)
    shortlink = data.get('url', url)
    return shortlink


class ImportHandler(webapp2.RequestHandler):

    def cache_daily_event(self, import_date):
        value = memcache.get(import_date)
        if DEBUG or not value:
            raw_events = get_events_on_date(import_date)
            raw_events = add_priority_to_events(raw_events)
            raw_events = add_keywords(raw_events)
            events = filter_events(raw_events, import_date)

            events = sort_events_by_priority(events)

            try:
                event = events[0]
                logging.info('EVENT FOUND!')
            except IndexError:
                logging.info('SQUARK: NO EVENTS FOUND')
                event = None
                if len(raw_events) > 0:
                    events = sort_events_by_priority(raw_events)
                    event = events[0]

            # Add in event date field
            event = add_event_date(event, import_date)
            logging.info(event)
            memcache.set(import_date, event, time=TWEET_MEMCACHE_TTL)
            # logging.info('Set: %s' % memcache.get(import_date))
            return event


    def get(self):
        for daycount in range(0, DAYS_TO_GET):
            scandate = format_date_from_memcache(daycount)
            self.cache_daily_event(scandate)
        self.response.write('<hr>')


class HeartBeatHandler(webapp2.RequestHandler):
    def get(self):
        """
        Regular (30mins) check to see if an event is about to start & tweet it
        """
        today = format_date_from_memcache(0)
        todays_event = memcache.get(today)
        starttimestr = todays_event['event_dt']
        start_time = datetime.strptime(starttimestr, '%Y-%m-%d %H:%M:%S').replace(tzinfo=LOCAL_TZ)
        if timedelta(minutes=10) < start_time - datetime.now(tz=LOCAL_TZ) < timedelta(minutes=40):
            tweet = craft_just_starting_tweet(event=todays_event)
            send_tweet(tweet, DEBUG)


class SevenDaySharerHandler(webapp2.RequestHandler):
    def get(self):
        """
        Shares upcoming events for the week
        """
        now = datetime.now(tz=LOCAL_TZ)
        offset = int(self.request.get('delta', 0))
        todays_count = 'count_%s' % format_date_from_memcache(offset)
        datetime_offset = memcache.get(todays_count) or 0
        event_datetime = format_date_from_memcache(datetime_offset + offset)
        event = memcache.get(event_datetime)

        if event and now < datetime.strptime(event['event_dt'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=LOCAL_TZ):
            tweet = craft_tweet(event)
            send_tweet(tweet, DEBUG)
        memcache.set(todays_count, datetime_offset+1, time=TWEET_MEMCACHE_TTL)


class HomeHandler(webapp2.RequestHandler):
    def get(self):

        data = {}
        data['events'] = []

        for daycount in range(0, DAYS_TO_GET):
            event_datetime = format_date_from_memcache(daycount)
            data['events'].append(memcache.get(event_datetime))

        template = jinja_environment.get_template('templates/main.html')
        self.response.out.write(template.render(data))


app = webapp2.WSGIApplication([
    ('/import', ImportHandler),
    ('/heartbeat', HeartBeatHandler),
    ('/sevendaysharer', SevenDaySharerHandler),
    ('.*', HomeHandler)
], debug=True)
