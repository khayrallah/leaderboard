import os
import sys
import time
import urllib

from collections import defaultdict

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

NUM_ASSIGNMENTS = 2

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(
    os.path.join(os.path.dirname(__file__), 'templates')),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

def key(user, id):
  return '%s / %s' % (user.user_id(), id)

class Assignment(ndb.Model):
  user = ndb.UserProperty()
  number = ndb.IntegerProperty()
  filename = ndb.StringProperty()
  filedata = ndb.TextProperty()
  score = ndb.FloatProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True)

class Handle(ndb.Model):
  user = ndb.UserProperty()
  leaderboard = ndb.BooleanProperty()
  handle = ndb.TextProperty()

class MainPage(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()

    user_handle = Handle.get_by_id(user.user_id())
    if user_handle is None:
      user_handle = Handle(id = user.user_id(), 
                           user = user, 
                           leaderboard = True, 
                           handle = user.nickname())
      user_handle.put()
      
    assignments = [None for x in range(NUM_ASSIGNMENTS)]
    for ass in Assignment.query(Assignment.user == user).fetch():
      if ass.number < len(assignments):
        assignments[ass.number] = ass
    for i in range(len(assignments)):
      if assignments[i] is None:
        user = users.get_current_user()
        assignments[i] = Assignment(id=key(user, i))
        assignments[i].user = user
        assignments[i].number = i
        assignments[i].datafile = None
        assignments[i].score = float("-inf")
        assignments[i].put()

    template_values = {
      'user': user.email(),
      'handle': user_handle.handle,
      'leaderboard': user_handle.leaderboard,
      'checked': 'checked' if user_handle.leaderboard else '',
      'logout': users.create_logout_url('/'),
      'assignments': assignments,
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')   
    self.response.write(template.render(template_values))

def score_sanity_check(filedata):
  value = filedata.split('\n')[0]
  try:
    return ((float(value)-1.0) % 100) + 1
  except ValueError:
    return -1

def score_dummy(filename):
  return 1.0

scorers = {
  '0': score_sanity_check,
  '1': score_dummy,
  '2': score_dummy,
  '3': score_dummy,
  '4': score_dummy,
  '5': score_dummy,
}

class Upload(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    number = self.request.get('number')
    assignment = Assignment.get_by_id(key(user, number))

    if assignment is None:
      print >> sys.stderr, "FATAL!"

    assignment.filedata = self.request.get('file')
    assignment.filename = self.request.POST.multi['file'].filename
    assignment.score = scorers.get(number)(assignment.filedata)
    assignment.put()

    self.redirect('/?')

class ChangeHandle(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    user_handle = Handle.get_by_id(user.user_id())
    user_handle.handle = self.request.get('handle')
    user_handle.leaderboard = (self.request.get('leaderboard') == 'True')
    user_handle.put()

    self.redirect('/?')

class LeaderBoard(webapp2.RequestHandler):
  def get(self):
    handles = {}
    for handle in Handle.query().fetch():
      if handle.leaderboard:
        handles[handle.user] = handle.handle

    scores = defaultdict(list)
    for a in Assignment.query().fetch():
      if handles.has_key(a.user):
        user_handle = handles[a.user]
        if not scores.has_key(user_handle):
          scores[user_handle] = [None for x in range(NUM_ASSIGNMENTS)]

        if a.number < NUM_ASSIGNMENTS:
          scores[user_handle][a.number] = a.score

    template = JINJA_ENVIRONMENT.get_template('leaderboard.js')
    template_values = {
      'scores': scores
    }

    self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/upload', Upload),
  ('/handle', ChangeHandle),
  ('/leaderboard.js', LeaderBoard),
], debug=True)