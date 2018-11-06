###############################
####### SETUP (OVERALL) #######
###############################

## Import statements
# Import statements
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, RadioField, SubmitField, ValidationError # Note that you may need to import more here! Check out examples that do what you want to figure out what.
from wtforms.validators import Required, Length # Here, too
from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager, Shell
import requests
import json
import datetime as dt
import http.client

## App setup code
app = Flask(__name__)
app.debug = True

## All app.config values
app.config['SECRET_KEY'] = 'superweirdhardtoguessstringydingy'
app.config["SQLALCHEMY_DATABASE_URI"] = 'postgresql://localhost/nbaappdb'
app.config['SQALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.jinja_env.add_extension('jinja2.ext.loopcontrols')

## Statements for db setup (and manager setup if using Manager)
manager = Manager(app)
db = SQLAlchemy(app)

######################################
######## HELPER FXNS (If any) ########
######################################

def validate_nba_date(form, field):
    today = dt.date.today()
    date_lst = field.data.split("-")
    try:
        date_entered = dt.date(int(date_lst[0]),int(date_lst[1]),int(date_lst[2]))
    except:
        raise ValidationError('Cmon bro! Not a valid date format!')
    if int(field.data[:4]) > 2018 or int(field.data[:4]) < 2013:
        raise ValidationError('Cmon bro! Pick the right year!')
    if date_entered >= today:
        raise ValidationError("Cmon Bro! Can't be today or in the future!")

def get_game_info(date):

    date = date.split('-')
    conn = http.client.HTTPSConnection("api.sportradar.us")

    conn.request("GET", "http://api.sportradar.us/nba/trial/v5/en/games/{}/{}/{}/schedule.json?api_key=kkj3ryukufht9s8578myqdg4".format(date[0], date[1], date[2]))

    res = conn.getresponse()
    data = res.read()
    clean = data.decode("utf-8").replace("'",'""')
    json_resp = json.loads(clean)

    game_info = {}
    game_info['date'] = json_resp['date']
    game_info['games'] = []
    games = json_resp['games']
    for a in games:
        if a['status'] == 'scheduled' or a['status'] == 'inprogress':
            home_points = 0
            away_points = 0
            winner = 'Game has not started or is in progress'
        else:
            home_points = a['home_points']
            away_points = a['away_points']
            if int(home_points) > int(away_points):
                winner = a['home']['name']
            else:
                winner = a['away']['name']

        game_info['games'].append({'home_team': a['home']['name'], 'away_team': a['away']['name'], 'home_team_points': home_points, 'away_team_points': away_points, 'winner': winner})

    return game_info

##################
##### MODELS #####
##################

class Name(db.Model):
    __tablename__ = 'names'
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String())
    posts = db.relationship('Post', backref = 'Name')

    def __repr__(self):
        return "{} (ID: {})".format(self.name, self.id)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key = True)
    post = db.Column(db.String(500))
    name_id = db.Column(db.Integer, db.ForeignKey('names.id'))

class Game_Score(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key = True)
    date = db.Column(db.Date)
    home_team = db.Column(db.String())
    away_team = db.Column(db.String())
    home_team_score = db.Column(db.Integer)
    away_team_score = db.Column(db.Integer)
    winner = db.Column(db.String())

class FavoritePlayer(db.Model):
    __tablename__ = 'favoriteplayers'
    id = db.Column(db.Integer, primary_key = True)
    player = db.Column(db.String())
    votes = db.Column(db.Integer())

###################
###### FORMS ######
###################

class PostForm(FlaskForm):
    name = StringField('Please enter your name: ', validators = [Required()])
    post = StringField('Write a prediction or thought about an upcoming or past game: ', validators = [Required(), Length(0, 500, message = 'Post must be between 1 and 500 characters long.')])
    submit = SubmitField()

class DateScores(FlaskForm):
    date = StringField('Enter the date of which NBA scores you\'d like to see: (Please use format YYYY-MM-DD, like: 2018-11-03, and only search years 2013-2018)', validators = [Required(), validate_nba_date])
    submit = SubmitField()

class BestPlayer(FlaskForm):
    player = RadioField('Who\'s the best player of all time?', choices = [('kobe bryant', 'Kobe Bryant'), ('lebron james', 'Lebron James'), ('michael jordan', 'Michael Jordan')], validators = [Required()])
    submit = SubmitField('Submit')

#######################
###### VIEW FXNS ######
#######################

@app.errorhandler(404)
def route_not_found(error):
    return render_template('404.html')

@app.route('/', methods=['GET','POST'])
def home():
    form = PostForm()

    if form.validate_on_submit():
        post_text = form.post.data
        post_author = form.name.data

        name_query = Name.query.filter_by(name = post_author).first()
        if not name_query:
            name = Name(name = post_author)
            db.session.add(name)
            db.session.commit()
        else:
            name = name_query

        post_query = Post.query.filter_by(post=post_text,name_id=name.id).first()
        if not post_query:
            post = Post(post = post_text, name_id = name.id)
            db.session.add(post)
            db.session.commit()
            flash("Post successfully submitted")
        else:
            flash("Post by this author already exists!")
            return redirect(url_for('get_all_posts'))

    form_errors = [a for a in form.errors.values()]
    if len(form_errors) > 0:
        flash("Error in form submission!" + str(form_errors))

    return render_template('base.html', form = form)

@app.route('/allposts')
def get_all_posts():
    all_posts = {a : Post.query.filter_by(name_id=a.id).all() for a in Name.query.all()}
    return render_template('all_posts.html', posts = all_posts)

@app.route('/game_scores')
def get_nba_date_form():
    form = DateScores()
    return render_template('game_scores.html', form = form)

@app.route('/game_scores_view', methods = ['GET'])
def game_scores_view():
    form = DateScores(request.args)
    if form.validate():
        date = form.date.data
        date_query = Game_Score.query.filter_by(date = date).first()
        if not date_query:
            game_info = get_game_info(str(date))
            game_date = game_info['date']
            for a in game_info['games']:
                game = Game_Score(date = game_date, home_team = a['home_team'], away_team = a['away_team'], home_team_score = a['home_team_points'], away_team_score = a['away_team_points'], winner = a['winner'])
                db.session.add(game)
                db.session.commit()
        games = Game_Score.query.filter_by(date = date).all()
        return render_template('game_scores_view.html', date = date, games = games)

    form_errors = [a for a in form.errors.values()]
    if len(form_errors) > 0:
        flash("Error in form submission!" + str(form_errors))
    return redirect('/game_scores')


@app.route('/bestplayer', methods = ['GET', 'POST'])
def whos_the_goat():
    form = BestPlayer()
    if form.validate_on_submit():
        best_player = form.player.data
        player_query = FavoritePlayer.query.filter_by(player = best_player).first()
        print(player_query)
        if not player_query:
            player = FavoritePlayer(player = best_player, votes = 1)
            db.session.add(player)
            db.session.commit()
        else:
            player_query.votes =  player_query.votes + 1
            db.session.commit()
            print(player_query.votes)
        return redirect("/votes")

    form_errors = [a for a in form.errors.values()]
    if len(form_errors) > 0:
        flash("Error in form submission!" + str(form_errors))
    return render_template('favorite_players.html', form = form)

@app.route('/votes')
def votes():
    player_votes = FavoritePlayer.query.all()
    favorite_player = sorted(player_votes,key = lambda x: x.votes,reverse=True)[0]
    return render_template('votes.html', players = player_votes, favorite_player = favorite_player)


## Code to run the application...

# Put the code to do so here!
# NOTE: Make sure you include the code you need to initialize the database structure when you run the application!

if __name__ == '__main__':
    db.create_all()
    manager.run()
    app.run(use_reloader=True,debug=True)
