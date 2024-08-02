from flask import Flask , render_template , request , redirect , jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime , date
import flask_login
import docker
import random
import threading
import time
import sqlite3
import config
import socket

#------------------------------(config app)-----------------------------------------





app = Flask(__name__ , template_folder='./template',static_folder='./template/static')
app.config['SECRET_KEY'] = 'something-secret'
login_manager = flask_login.LoginManager(app)
limiter = Limiter(get_remote_address,app=app,default_limits=["200 per day", "50 per hour"])
client = docker.from_env()  
num = 0
lunches = 0
kills = 0
info = {}
users = {config.ADMIN_USERNAME: {'password': config.ADMIN_PASSWORD}}
class User(flask_login.UserMixin):
    pass

#------------------------------(config login)--------------------------------------

@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return

    user = User()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    user = request.form.get('username')
    if user not in users:
        return

    user = User()
    user.id = user
    return user


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect('/login')


#------------------------------(any function)--------------------------------------


class GeneralSetting():
    def __init__(self,limit_number,minimum_time,puse=False):
        self.limit_number = limit_number
        self.minimum_time = minimum_time
        self.puse = puse
    def format(self):
        data = {"num_lim":self.limit_number , "min_time":self.minimum_time , "puse": ""}
        if self.puse:
            data['puse'] = "checked"
        return data
        
    
general_setting = GeneralSetting(0,0)



def check_port(port): #checking port is free
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = (list(config.BASE_URL.split("//"))[1][:-1], port)
    result_of_check = a_socket.connect_ex(location)
    if result_of_check == 0:
        return False
    return True


def check_challange(id):
    keys = challanges.keys()
    for k in keys:
        if id == k:
            return True
    return False


def handel_container(container,tim,port):
    global kills
    tim = tim - 8
    time.sleep(tim)
    container.stop()
    container.remove()
    kills+=1
    log(f"KILL CONTAINER ContainerName:{container.name}")

def find_port():
    start_range_port = config.RANGE_PORT[0]
    end_range_port = config.RANGE_PORT[1]
    server_port = random.randint(start_range_port,end_range_port)
    while True:
        if check_port(server_port):
            return server_port
        else :
            server_port = random.randint(start_range_port,end_range_port)

def get_images():
    data = client.images.list()
    answer = []
    for i in range(len(data)):
        x = data[i].attrs
        answer.append({'num':i+1,'name':x['RepoTags'][0],"id":list(x["Id"].split(":"))[1][:12],'size':x['Size']}) 
    return answer


def get_challanges():
    data_struct = ['id','name','time','port','command','dis']
    try :
        conection = sqlite3.connect("challanges.db")
        courser = conection.cursor()
        courser.execute(f"""SELECT * FROM challanges;""")
        data = courser.fetchall()
        conection.close()
        data_pars = {}
        for d in data:
            const = d[0]
            iter = data_pars[const] = {}
            for i in range(6):
                iter[data_struct[i]] = d[i]
        return data_pars
    except :
        return {}




def get_containers():
    data = client.containers.list()
    ans = []
    j=1
    for i in data:
        x = i.attrs
        name = x['Name'][1:]
        image = x['Config']['Image']
        network = x["NetworkSettings"]["Ports"]
        key = list(network)[0]
        lp = key.split("/")[0]
        protocol = key.split("/")[1]
        rp = network[key][0]['HostPort']
        ans.append({'num':j,'name':name,'image':image,'port':f"{rp}:{lp}",'pro':protocol})
        j+=1
    return ans

def log(action):
    log_file = open(config.LOG_FILE_PATH,"a")
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    today = date.today()
    formatted_date = today.strftime('%B %d, %Y')
    data = f"[{current_time}]   [{formatted_date}]   {action}\n"
    log_file.write(data)
    log_file.close()


def remove_all_container():
    global client
    global kills
    containers = client.containers.list()
    for container in containers:
        container.stop()
        container.remove()
        kills+=1






#------------------------------(error handling)--------------------------------------



@app.errorhandler(429)
def limiter_handel_error(e):
    error = {"status":429,"text":"Too Many Requests"}
    return render_template("error.html",error=error)


@app.errorhandler(404)
def handel_404_error(e):
    error = {'status':404,'text':"Page not found"}
    return render_template("error.html",error=error)





#------------------------------(pages)--------------------------------------


@app.route("/login",methods=['GET',"POST"])
@limiter.limit("3/minute",override_defaults=False)
def login():
    if request.method == "GET" :
        return render_template('login.html')
    else :
        username = request.form['username']
        if username in users and request.form['password'] == users[username]['password']:
            user = User()
            user.id = username
            flask_login.login_user(user)
            return redirect('/admin')
        return 'Bad login'




@app.route("/admin",methods=['GET',"POST"])
@flask_login.login_required
def admin_page():
    global general_setting
    if general_setting.puse:
        t2 = threading.Thread(target=remove_all_container)
        t2.start()
    images = get_images()
    containers = get_containers()
    challanges = get_challanges()
    challanges_list = []
    for challange in challanges:
        challanges_list.append(challanges[challange])
    images_name = []
    for i in images:
        images_name.append(i['name'])
    return render_template("admin.html",info={'total':len(images),'up':len(containers),'lunch':lunches,'kills':kills},images=images,con=containers,challanges=challanges_list,gs=general_setting.format())

@app.route("/admin/new_challange",methods=["POST"])
@limiter.limit("3/minute",override_defaults=False)
@flask_login.login_required
def new_challange():
    challange_id = request.form['id']
    image_name = request.form['name']
    life_time = request.form['time']
    lport = request.form['port']
    command = request.form['command']
    dis = request.form['discription']
    conection = sqlite3.connect("challanges.db")
    create_table_query = """CREATE TABLE IF NOT EXISTS challanges (
        id TEXT,
        name TEXT,
        life_time INT,
        port INT,
        command TEXT,
        dis TEXT
        );"""
    conection.execute(create_table_query)
    courser = conection.cursor()
    courser.execute(f"""INSERT INTO challanges (id,name,life_time,port,command,dis) VALUES ('{challange_id}','{image_name}','{int(life_time) * 60}','{int(lport)}','{command}','{dis}');""")
    conection.commit()
    conection.close()
    log(f"CREATE NEW CHALLANGE IN DATABASE ChallangeName:{image_name}")
    return redirect("/admin")
    
    



@app.route("/challange/<id>",methods=['GET',"POST"])
@limiter.limit("4/minute",override_defaults=False)
def main(id:str):
    global client
    global lunches
    global challanges
    global info
    global general_setting
    challanges = get_challanges()
    if request.method == "GET":
        return render_template("index.html",e = "")
    else :
        if check_challange(id):
            if len(get_containers()) >= general_setting.limit_number and general_setting.limit_number != 0:
                error = {"status":"TOO MANY CONTAINERS UP","text":"please try another time"}
                return render_template("error.html",error=error)
            if general_setting.puse:
                error = {"status":"CHALLANGES IS STOP","text":""}
                return render_template("error.html",error=error)
            server_port = find_port()
            challange = challanges[id]
            cantainer=client.containers.run(challange['name'],challange['command'],ports={int(challange['port']):server_port},detach=True,stdout=False)
            url = config.BASE_URL + str(server_port)
            data = {"name":challanges[id]['name'],"server":url,"time":int(challange['time']),'dis':challange['dis']}
            info[challange['id']] += 1
            tim= int(challange['time'])
            t2 = threading.Thread(target=handel_container,args=(cantainer,tim,server_port))
            t2.start()
            log(f"CREATING NEW CONTAINER ContainerName:{cantainer.name}")
            lunches+=1
            return render_template("index.html",data=data)
        else:
            return render_template("index.html" , e ="faild id challange")

@app.route("/admin/remove_image")
@flask_login.login_required
def remove_image():
    name = request.args['name']
    client.images.remove(image=name,force=True)
    log(f"REMOVING IMAGE ImageName:{name}")
    return redirect("/admin")

@app.route("/admin/remove_challange")
@flask_login.login_required
def remove_challange():
    id = request.args['id']
    try:
        conection = sqlite3.connect("challanges.db")
        courser = conection.cursor()
        query = f"""DELETE FROM challanges WHERE id = '{id}';"""
        courser.execute(query)
        conection.commit()
        conection.close()
        log(f"REMOVING CHALLANGE FROM DATABSE Challange id={id}")
        return redirect("/admin")
    except sqlite3.Error as e:
        print(e)
        return redirect("/admin")
    
@app.route("/admin/inspect")
@flask_login.login_required
def inspect():
    global client
    if "name" in request.args:
        try:
            name = request.args['name']
            container = client.containers.get(name)
            return jsonify(container.attrs)
        except:
            error = {"status":"container not found","text":""}
            return render_template("error.html",error=error)
    else:
        return redirect("/admin")
@app.route("/admin/container_logs")
@flask_login.login_required
def get_container_logs():
    global client
    if "name" in request.args:
        try:
            name = request.args['name']
            container = client.containers.get(name)
            return container.logs().decode()
        except:
            return "Container is not Live"
    else:
        return ""
    
@app.route("/admin/run_command" , methods=['POST'])
@flask_login.login_required
def exec_command():
    try:
        container_name = request.args['name']
        conatiner = client.containers.get(container_name)
        command = request.get_json()['command']
        response = conatiner.exec_run(command).output
        return response.decode()
    except:
        return "ERROR: this requests is not OK!!!"
    
@app.route("/admin/kill_container")
@flask_login.login_required
def kill_container():
    global kills
    container_name = request.args['name']
    container = client.containers.get(container_name)
    container.stop()
    container.remove()
    kills+=1
    log(f"KILL CONTAINER BY Admin panel ContainerName:{container_name}")
    return redirect('/admin')

@app.route("/admin/statistic")
@flask_login.login_required
def statistic():
    global info
    challanges = get_challanges()
    for id in challanges:
        challange_name = challanges[id]['id']
        if challange_name not in info.keys():
            info[challange_name] = 0
    return jsonify(info)


@app.route("/admin/change_challange",methods=['GET',"POST"])
@flask_login.login_required
def change_challange():
    id = request.args['id']
    challanges = get_challanges()
    if id in challanges:
        if request.method == "POST":
            conection = sqlite3.connect("challanges.db")
            courser = conection.cursor()
            post_argument = request.form        
            courser.execute(f"""UPDATE challanges SET name='{post_argument['name']}', life_time={post_argument['time']} , port={post_argument['port']} ,command='{post_argument['command']}', dis='{post_argument['discription']}' WHERE id='{id}';""")
            conection.commit()
            conection.close()
            return redirect("/admin")
        else:
            return jsonify(challanges[id])
    else:
        error = {"status":"error","message":"challange is not define"}
        return jsonify(error)

@app.route("/admin/status")
def status():
    data = {}
    containers = client.containers.list()
    for container in containers:
        status = container.stats(decode=None,stream=False)
        name = container.name
        cpu = status['cpu_stats']['cpu_usage']['total_usage']
        memory = status['memory_stats']['usage']
        network = status['networks']['eth0']['rx_bytes']
        data[name]={"cpu":cpu,"memory":memory,"net":network}
    return data

@app.route("/admin/pull")
@flask_login.login_required
def pull_image():
    global client
    name = request.args['name']
    t1 = threading.Thread(target=client.images.pull,args=(name,))
    t1.start()
    log(f"START PULL IMAGE ImageName={name}")
    return redirect("/admin")
@app.route("/admin/change_genral_setting",methods=["POST"])
@flask_login.login_required
def change_login_required():
    global general_setting
    general_setting.limit_number = int(request.form['num_lim'])
    general_setting.minimum_time = int(request.form['min_time'])
    if "puse" in request.form:
        general_setting.puse = True
    else:
        general_setting.puse = False
    return redirect("/admin")
    
    

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect('/admin')



#------------------------------(RUN app)--------------------------------------


if __name__ == "__main__":
    app.run(debug=True)