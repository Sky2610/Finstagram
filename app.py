from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finsta",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    name = session["username"]
    with connection.cursor() as cursor:
        query = "SELECT bio FROM person WHERE username = %s"
        cursor.execute(query, (name))
    data = cursor.fetchone()
    return render_template("home.html", username=name, bio=data)

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    name = session["username"]
    with connection.cursor() as cursor:
        query = "SELECT groupName, groupOwner FROM Belong WHERE username = %s"
        cursor.execute(query, (name))
        data = cursor.fetchall()
    return render_template("upload.html", groups = data)

@app.route("/bio", methods=["GET"])
@login_required
def bio():
    return render_template("bio.html")

@app.route("/groups", methods=["GET"])
@login_required
def groups():
    name = session["username"]
    with connection.cursor() as cursor:
        query1 = "SELECT groupName FROM CloseFriendGroup WHERE groupOwner = %s"
        cursor.execute(query1, (name))
        data1 = cursor.fetchall()
    return render_template("mygroups.html", groups = data1)

@app.route("/images", methods=["GET"])
@login_required
def images():
    user = session["username"]
    query = "SELECT photoID, photoOwner, timestamp, filePath FROM photo WHERE (photoID, photoOwner, timestamp, filePath) IN "
    query = query + "(SELECT photoID, photoOwner, timestamp, filePath FROM photo WHERE photo.photoOwner = %s) OR (photoID, photoOwner, timestamp, filePath) IN "
    query = query + "(SELECT photoID, photoOwner, timestamp, filePath FROM photo JOIN follow ON photo.photoOwner = follow.followeeUsername WHERE follow.followerUsername = %s AND follow.acceptedfollow = True AND photo.allFollowers = True) OR (photoID, photoOwner, timestamp, filePath) IN "
    query = query + "(SELECT DISTINCT p.photoID, p.photoOwner, p.timestamp, p.filePath FROM photo AS p NATURAL JOIN share NATURAL JOIN belong WHERE belong.username = %s AND belong.groupName IN (SELECT belong.groupName FROM photo JOIN belong WHERE p.photoOwner = belong.username))"
    query = query + "ORDER BY timestamp DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, (user, user, user))
    data = cursor.fetchall()
    for i in data:
        photoID = i["photoID"]
        query2 = "SELECT fname, lname FROM person NATURAL JOIN tag WHERE photoID = %s AND acceptedTag = True"
        with connection.cursor() as cursor:
            cursor.execute(query2, (photoID))
        taggees = cursor.fetchall()
        taglst = []
        for oneDict in taggees:
            taglst.append((oneDict["fname"], oneDict["lname"]))
        i['taggees'] = taglst
        
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/tagAuth", methods=["GET", "POST"])
@login_required
def tagAuth():
    if request.form:
        user = session["username"]
        requestData = request.form
        taggee = requestData["taggee"]
        photoID = requestData["photoID"]
        if taggee == "":
            error = "No user entered!"
            return render_template('error.html', error = error)
        with connection.cursor() as cursor:
            query1 = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query1, (taggee))
            data = cursor.fetchall()
            if len(data) == 0:
                error = "User not found!"
                return render_template('error.html', error = error)
        if taggee == user:
            try:
                query3 = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query3, (user, photoID, False))
            except pymysql.err.IntegrityError:
                error = "User is already tagged or has been requested to be tagged!"
                return render_template('error.html', error = error)
            success = "Tag request successfully sent."
            return render_template('success.html', success = success)
        with connection.cursor() as cursor:
            query2 = "SELECT username FROM person WHERE username IN "
            query2 = query2 + "(SELECT DISTINCT username FROM share NATURAL JOIN belong WHERE share.photoID = %s AND belong.username = %s) OR username IN "
            query2 = query2 + "(SELECT follow.followerUsername FROM follow JOIN photo ON photo.photoOwner = follow.followeeUsername WHERE follow.followerUsername = %s AND follow.acceptedfollow = True AND photo.photoID = %s AND photo.allFollowers = True) OR username IN "
            query2 = query2 + "(SELECT photoOwner FROM photo WHERE photoID = %s AND photoOwner = %s)"
            cursor.execute(query2, (photoID, taggee, taggee, photoID, photoID, taggee))
            data = cursor.fetchall()
            if len(data) == 0:
                error = "User cannot view this post!"
                return render_template('error.html', error = error)

        try:
            query4 = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                cursor.execute(query4, (taggee, photoID, False))
        except pymysql.err.IntegrityError:
            error = "User is already tagged or has been requested to be tagged!"
            return render_template('error.html', error = error)
        
        success = "Tag request successfully sent."
        return render_template('success.html', success = success)

    error = "An error has occurred. Please try again."
    return render_template("error.html", error=error) 
            
        

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/bioAuth", methods=["POST"])
def bioAuth():
    if request.form:
        requestData = request.form
        bio = requestData["bio"]
        with connection.cursor() as cursor:
            query = "UPDATE person SET bio = %s WHERE username = %s"
            cursor.execute(query, (bio, session["username"]))
        return redirect(url_for("home"))
    error = "An error has occurred. Please try again."
    return render_template("bio.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")


  

@app.route("/createGroup", methods=["POST"])
@login_required
def create_group():
    if request.form:
        user = session["username"]
        requestData = request.form
        newgroup = requestData["newgroup"]
        try:
            with connection.cursor() as cursor:
                query1 = "INSERT INTO CloseFriendGroup (groupName, groupOwner) VALUES (%s, %s)"
                cursor.execute(query1, (newgroup, user))
        except pymysql.err.IntegrityError:
            error = "You already own a group called %s" % (newgroup)
            return render_template('error.html', error = error)

        with connection.cursor() as cursor:
            query2 = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
            cursor.execute(query2, (newgroup, user, user))
        return redirect(url_for("groups"))

    error = "An error has occurred. Please try again."
    return render_template("error.html", error=error)

@app.route("/addMember", methods=["GET", "POST"])
def add_member():
    if request.form:
        user = session["username"]
        requestData = request.form
        newmember = requestData["newmember"]
        if newmember == "":
            error = "No name entered!"
            return render_template('error.html', error = error)
        with connection.cursor() as cursor:
            query1 = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query1, (newmember))
            data = cursor.fetchall()
            if len(data) == 0:
                error = "User not found!"
                return render_template('error.html', error = error)

        if "grouplist" not in requestData:
            error = "You didn't choose a group!"
            return render_template('error.html', error = error)
                
        group = requestData["grouplist"]
        try:
            with connection.cursor() as cursor:
                query2 = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
                cursor.execute(query2, (group, user, newmember))
        except pymysql.err.IntegrityError:
            error = "User already in that group!"
            return render_template('error.html', error = error)

        success = "User successfully added!"
        return render_template('success.html', success = success)

    error = "An error has occurred. Please try again."
    return render_template("error.html", error=error)


@app.route("/follow", methods=["GET"])
@login_required
def follow():
    name = session["username"]
    with connection.cursor() as cursor:
        query1 = "SELECT followeeUsername FROM Follow WHERE followerUsername = %s AND acceptedfollow = False"
        cursor.execute(query1, (name))
        data1 = cursor.fetchall()
        query2 = "SELECT followeeUsername FROM Follow WHERE followerUsername = %s AND acceptedfollow = True"
        cursor.execute(query2, (name))
        data2 = cursor.fetchall()
    return render_template("follow.html", pending = data1, following = data2)


@app.route("/followAuth", methods=["GET", "POST"])
@login_required
def followAuth():
    if request.form:
        user = session["username"]
        requestData = request.form
        followee = requestData["followee"]
        if followee == "":
            error = "No name entered!"
            return render_template('error.html', error = error)
        with connection.cursor() as cursor:
            query1 = "SELECT * FROM person WHERE username = %s"
            cursor.execute(query1, (followee))
            data = cursor.fetchall()
            if len(data) == 0:
                error = "User not found!"
                return render_template('error.html', error = error)
        try:
            with connection.cursor() as cursor:
                query2 = "INSERT INTO Follow (followerUsername, followeeUsername, acceptedFollow) VALUES (%s, %s, %s)"
                cursor.execute(query2, (user, followee, False))
        except pymysql.err.IntegrityError:
            error = "Already following this user!"
            return render_template("error.html", error = error)

        success = "Request successfully submitted. Please wait for them to accept your follow."
        return render_template('success.html', success = success)

    error = "An error has occurred. Please try again."
    return render_template("error.html", error=error)


@app.route("/acceptFollow", methods=["GET"])
@login_required
def acceptFollow():
    name = session["username"]
    with connection.cursor() as cursor:
        query1 = "SELECT followerUsername FROM Follow WHERE followeeUsername = %s AND acceptedfollow = False"
        cursor.execute(query1, (name))
        data1 = cursor.fetchall()
        query2 = "SELECT followerUsername FROM Follow WHERE followeeUsername = %s AND acceptedfollow = True"
        cursor.execute(query2, (name))
        data2 = cursor.fetchall()
    return render_template("acceptFollow.html", requests = data1, followers = data2)

@app.route("/acceptfollowAuth", methods=["GET", "POST"])
@login_required
def acceptfollowAuth():
    if request.form:
        user = session["username"]
        requestData = request.form
        accept = requestData["accepted"]
        follower = requestData["followerUsername"]
        if accept == "true":
            with connection.cursor() as cursor:
                query = "UPDATE Follow SET acceptedFollow = True WHERE followeeUsername = %s and followerUsername = %s"
                cursor.execute(query, (user, follower))
        else:
            with connection.cursor() as cursor:
                query2 = "DELETE FROM Follow WHERE followeeUsername = %s AND followerUsername = %s"
                cursor.execute(query2, (user, follower))
        return redirect(url_for("follow"))

@app.route("/acceptTag", methods=["GET"])
@login_required
def acceptTag():
    name = session["username"]
    with connection.cursor() as cursor:
        query = "SELECT * FROM tag NATURAL JOIN photo WHERE tag.username = %s AND acceptedTag = False"
        cursor.execute(query, (name))
        data = cursor.fetchall()
    return render_template("acceptTag.html", photos = data)

@app.route("/acceptTagAuth", methods=["GET", "POST"])
@login_required
def acceptTagAuth():
    if request.form:
        user = session["username"]
        requestData = request.form
        if "accepted" not in requestData:
            error = "You didn't choose an option!"
            return render_template('error.html', error = error)
        accept = requestData["accepted"]
        photoID = requestData["photoID"]
        if accept == "true":
            with connection.cursor() as cursor:
                query = "UPDATE tag SET acceptedTag = True WHERE username = %s AND photoID = %s"
                cursor.execute(query, (user, photoID))
        elif accept == "false":
            with connection.cursor() as cursor:
                query2 = "DELETE FROM tag WHERE username = %s AND photoID = %s"
                cursor.execute(query2, (user, photoID))
        return redirect(url_for("acceptTag"))
        
@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        user = session["username"]
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        if image_name == "":
            message = "You need to upload a file in order to submit!"
            return render_template("error.html", error=message)
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        if request.form:
            requestData = request.form
            allfollowers = requestData["allFollowers"]
            if allfollowers == "Yes":
                query1 = "INSERT INTO photo (photoOwner, timestamp, filePath, allFollowers) VALUES (%s, %s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query1, (user, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, True))
            else:
                query2 = "INSERT INTO photo (photoOwner, timestamp, filePath, allFollowers) VALUES (%s, %s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query2, (user, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, False))
            photoID = cursor.lastrowid
            listofgroups = requestData.keys()
            for group in listofgroups:
                if group != "allFollowers":
                    groupOwner = requestData[group]
                    with connection.cursor() as cursor:
                        query3 = "INSERT INTO Share (groupName, groupOwner, photoID) VALUES (%s, %s, %s)"
                        cursor.execute(query3, (group, groupOwner, photoID))
    
            success = "Image has been successfully uploaded."
            return render_template("success.html", success=success)

    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
