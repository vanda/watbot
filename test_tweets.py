__author__ = 'julz'

from unittest import TestCase
from main import construct_tweet, add_ordinal

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

    def test_ordinal_basic(self):
        self.assertEquals('1st', add_ordinal(1))
        self.assertEquals('2nd', add_ordinal(2))
        self.assertEquals('3rd', add_ordinal(3))
        self.assertEquals('4th', add_ordinal(4))

    def test_ordinal_large_numbers(self):
        self.assertEquals('1111st', add_ordinal(1111))
        self.assertEquals('12346th', add_ordinal(12346))

    def test_ordinal_numberic_string(self):
        self.assertEquals('4th', add_ordinal("4"))

    def test_ordinal_string(self):
        self.assertRaises(TypeError, add_ordinal("this is a string"))