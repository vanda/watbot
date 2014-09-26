#!/usr/bin/env python
import ConfigParser
from datetime import datetime, timedelta
import json
import os
import urllib2
import webapp2
import jinja2
import tweepy

from roomlookup import ROOMLOOKUPDICT

WORKSHOP = 15
SPECIAL_EVENT = 24
EVENING_TALK_CODE = 40
DAILY_TOUR_CODE = 41
BSL_TALK = 42
SEMINAR = 44
MEMBERSHIP_EVENT_CODE = 45


jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


def days_delta(n):
    return timedelta(days=n)



def get_first_int_in_list(src_list):
    for i in src_list:
        try:
            return(int(i))
        except ValueError:
            pass
            
def send_tweet(msg):
    config = ConfigParser.RawConfigParser()
    config.read('settings.cfg')
    CONSUMER_KEY = config.get('Twitter OAuth', 'CONSUMER_KEY')
    CONSUMER_SECRET = config.get('Twitter OAuth', 'CONSUMER_SECRET')
    ACCESS_TOKEN_KEY = config.get('Twitter OAuth', 'ACCESS_TOKEN_KEY')
    ACCESS_TOKEN_SECRET = config.get('Twitter OAuth', 'ACCESS_TOKEN_SECRET')
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    result = api.update_status(msg)
    return result


class MainHandler(webapp2.RequestHandler):
    ''' prints to screen the cal
    '''

    def get(self):
        for daycount in range(0,6):
            scandate = (datetime.now() + days_delta(daycount)).strftime("%Y%m%d")
            self.response.write('<h2>%s</h2>' % scandate )
            urlpath = "http://www.vam.ac.uk/whatson/json/events/day/%s/" % scandate
            response = urllib2.urlopen(urlpath)
            data = json.load(response)
            for d in data:
                if d['fields']['event_type'] not in [EVENING_TALK_CODE, DAILY_TOUR_CODE, MEMBERSHIP_EVENT_CODE, 24 ]:
                    continue
                if 'TOUR' in d['fields']['short_description']:
                    continue
                # self.response.write(d['pk'])
                # self.response.write(d)
                self.response.write('<img src="http://www.vam.ac.uk/whatson/media/%s" style="width:250px;"><br>' % d['fields']['image'])
                for f in ['name','first_slot','last_slot', 'short_description','event_type',
                          'free','image','location']:
                    self.response.write('%s: %s' % (f, d['fields'][f]))
                    dur = datetime.strptime(d['fields']['last_slot'], '%Y-%m-%d %H:%M:%S') - datetime.strptime(d['fields']['first_slot'], '%Y-%m-%d %H:%M:%S')
                    self.response.write('<br>' )
                self.response.write('<br>duration: %s' % dur )
                try:
                    self.response.write('<br>location: %s' % ROOMLOOKUPDICT[str(d['fields']['location'])]['loc_name']  )
                except KeyError:
                    self.response.write('location: ?')
                # if dur > timedelta(days=5):
                #     self.response.write('<br>long event!' )
                self.response.write('<hr>')


class EventHandler(webapp2.RequestHandler):
    def get_events_on_date(self, scandate):
        urlpath = "http://www.vam.ac.uk/whatson/json/events/day/%s/" % scandate
        response = urllib2.urlopen(urlpath)
        data = json.load(response)
        return data

    def filter_irrelevant_events(self, events):
        relevant = []
        for d in events:
            if d['fields']['event_type'] in [WORKSHOP, SPECIAL_EVENT, EVENING_TALK_CODE, BSL_TALK, SEMINAR, MEMBERSHIP_EVENT_CODE]:
                relevant.append(d)
        return relevant

    def prioritise_relevant_events(self, events):
        for i, d in enumerate(events):

            if 'Friday Late' in d['fields']['name']:
                events.insert(0, events.pop(i))

        return events

    def write_tweet(self, event):
        # print 'Name: %s' % event['fields']['name'].encode('utf8')
        # print 'Event type: %s' % event['fields']['event_type']
        # print 'Desc: %s' % event['fields']['short_description'].encode('utf8')
        # print '#'*16

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

        event_datetime = datetime.strptime(event['fields']['last_slot'], '%Y-%m-%d %H:%M:%S')
        display_day = add_ordinal(strip_leading_zero(event_datetime.strftime('%d')))
        display_month = event_datetime.strftime('%b')
        display_time = event_datetime.strftime('%H:%M')
        display_url = 'http://www.vam.ac.uk/whatson/event/%s' % event['pk']

        tweet = '%s %s %s: %s | %s' % (display_day, display_month, display_time, event['fields']['name'].encode('utf8'), display_url)

        return tweet

    def get(self):
        for daycount in range(0, 7):
            scandate = (datetime.now() + days_delta(daycount)).strftime("%Y%m%d")
            events = self.get_events_on_date(scandate)
            events = self.filter_irrelevant_events(events)
            events = self.prioritise_relevant_events(events)
            try:
                event = events[0]
                tweet = self.write_tweet(event)
                self.response.write(tweet)
                self.response.write('<hr>')
            except(IndexError):
                pass



class HomeHandler(webapp2.RequestHandler):
    def get(self):
        template = jinja_environment.get_template('templates/main.html')
        self.response.out.write(template.render({}))


app = webapp2.WSGIApplication([
    ('/events', EventHandler),
    ('/cal', MainHandler),
    ('.*', HomeHandler)
], debug=True)
