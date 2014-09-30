__author__ = 'julz'

from unittest import TestCase
from main import construct_tweet
from vector import Document

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

class TestKeywords(TestCase):
    def setUp(self):
        self.s = """
             The shuttle Discovery, already delayed three times by technical problems
             and bad weather, was grounded again Friday, this time by a potentially
             dangerous gaseous hydrogen leak in a vent line attached to the ships
             external tank. The Discovery was initially scheduled to make its 39th
             and final flight last Monday, bearing fresh supplies and an intelligent
             robot for the International Space Station. But complications delayed the
             flight from Monday to Friday,  when the hydrogen leak led NASA to conclude
             that the shuttle would not be ready to launch before its flight window
             closed this Monday. """
    def test_keyword_raw(self):
        s = self.s
        d = Document(s, threshold=1)
        results = d.keywords(top=6)
        results = [(round(i,2),j) for (i,j) in results]

        known = [(0.17, u'flight'), (0.17, u'monday'),
         (0.11, u'delayed'), (0.11, u'discovery'),
         (0.11, u'friday'), (0.11, u'hydrogen')]
        self.assertEquals(results,known)
    def test_keyword_cooked(self):
        s = self.s
        from main import extract_keywords
        results = extract_keywords(s,6)
        known = [(0.17, u'flight'), (0.17, u'monday'),
         (0.11, u'delayed'), (0.11, u'discovery'),
         (0.11, u'friday'), (0.11, u'hydrogen')]
        known_list = [j for (i,j) in known]
        self.assertEquals(results, known_list)

if __name__ == '__main__':
    unittest.main()