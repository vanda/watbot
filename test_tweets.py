__author__ = 'julz'

from unittest import TestCase
from main import construct_tweet

class TestFunctions(TestCase):
    def test_construct_tweet(self):
        c = construct_tweet(display_datetime='1st jan 2014', display_url='www.google.com',
                            event_title='the first event')
        self.assertEquals(c,'1st jan 2014: the first event | www.google.com')

    def test_construct_long_tweet(self):
        c = construct_tweet(display_datetime='1st jan 2014', display_url='www.google.com',
                            event_title='the first event'*10)
        self.assertEquals(c,'1st jan 2014: the first eventthe first eventthe first eventthe first eventthe first eventthe first eventthe first eventt... | www.google.com')
        self.assertTrue(len(c)<=140)

