#!/usr/bin/env python
from datetime import datetime, timedelta
import json
import os
import urllib2
import webapp2
import jinja2

from roomlookup import ROOMLOOKUPDICT

EVENING_TALK_CODE = 40
MEMBERSHIP_EVENT_CODE = 45
DAILY_TOUR_CODE = 41

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


def days_delta(n):
    return timedelta(days=n)



def get_first_int_in_list(src_list):
    for i in src_list:
        try:
            return(int(i))
        except ValueError:
            pass
            


class MainHandler(webapp2.RequestHandler):
    ''' prints to screen the cal
    '''
    def get(self):
        for daycount in range(0,28):
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



class HomeHandler(webapp2.RequestHandler):
    def get(self):
        template = jinja_environment.get_template('templates/main.html')
        self.response.out.write(template.render({}))


app = webapp2.WSGIApplication([
    ('/cal', MainHandler),
    ('.*', HomeHandler)
], debug=True)
