from queue import Queue
import time
import random
import threading
from PIL import Image
import flask
from flask import request
import json
import io
import uuid
import base64

id_read_from_form=1
user_counter = 1
global_diagnostic_strings = "START<br>"

### You create a Queue and start a scheduler, Start flask after that
def run_scheduler(app):
    global global_diagnostic_strings
    sleep_time = 1.5
    while True:
        time.sleep(sleep_time)
        print('jobs Completed ->',app.jobs_completed)

        if app.jobs_to_be_processed_queue.qsize() > 0:
            print(f"qsize={app.jobs_to_be_processed_queue.qsize()}")
            global_diagnostic_strings += "queue size = "+str(app.jobs_to_be_processed_queue.qsize()) + "<br>"
            next_job_name = app.jobs_to_be_processed_queue.get()
            print(f"No jobs being processed so scheduler will start processing the next image {next_job_name} from the queue")
            app.function_to_actually_crunch_the_numbers(next_job_name, app)
        else:
            global_diagnostic_strings += "queue size = "+str(app.jobs_to_be_processed_queue.qsize()) + "<br>"
            print("Pass")
            pass

def function_to_actually_crunch_the_numbers(job_name, app):
    global global_diagnostic_strings
    huge_number = 100

    for i in range(huge_number):
        # some maths
        percentage_done = str((i+1)*100/huge_number)
        app.job_processing_status_dict[job_name] = percentage_done
        time.sleep(.2)

    app.job_processing_status_dict[job_name] = str(100.0)  # done!

    R = random.randint(0,256)
    G = random.randint(0,256)
    B = random.randint(0,256)
    img = Image.new('RGB', (60, 30), color =(R,G,B))
    chunk_of_ram=io.BytesIO()

    img.save(chunk_of_ram, "jpeg")
    app.jobs_completed[job_name] = {"status":1,"file": chunk_of_ram}
    print(f"IC from function: {app.jobs_completed} **************************")

    if app.job_processing_status_dict.get("num_jobs_completed",False):
        global_diagnostic_strings += "app.job_processing_status_dict['num_jobs_completed'] incremented from "+str(app.job_processing_status_dict["num_jobs_completed"])+"<br>"
        app.job_processing_status_dict["num_jobs_completed"] += 1
    else:
        app.job_processing_status_dict["num_jobs_completed"] = 1
        global_diagnostic_strings += "app.job_processing_status_dict['num_jobs_completed'] being set to 1<br>"

    del app.job_processing_status_dict[job_name]     # The del keyword is used to delete objects. 

    return 0 #process sucessful

class Webserver(flask.Flask):
    def __init__(self,*args,**kwargs):
        scheduler_func = kwargs["scheduler_func"]
        function_to_actually_crunch_the_numbers = kwargs["function_to_actually_crunch_the_numbers"]
        queue_MAXSIZE = kwargs["queue_MAXSIZE"]
        del kwargs["function_to_actually_crunch_the_numbers"], kwargs["scheduler_func"], kwargs["queue_MAXSIZE"]
        super(Webserver, self).__init__(*args, **kwargs)
        self.start_time = time.strftime("%d/%m/%Y %H:%M")
        self.queue_MAXSIZE = queue_MAXSIZE
        self.active_processing_threads = []
        self.job_processing_status_dict = {}
        self.jobs_completed = {}
        self.jobs_to_be_processed_queue = Queue(maxsize=queue_MAXSIZE)
        self.function_to_actually_crunch_the_numbers = function_to_actually_crunch_the_numbers
        self.scheduler_thread = threading.Thread(target=scheduler_func, args=(self,))


app = Webserver(__name__,
                  template_folder="./templates",
                  static_folder="./",
                  static_url_path='',
                  scheduler_func = run_scheduler,
                  function_to_actually_crunch_the_numbers = function_to_actually_crunch_the_numbers,
                  queue_MAXSIZE = 20,
                 )


### You define a bunch of views
@app.route("/",methods=["GET"])
def render_basic_whole_webpage():
    global global_diagnostic_strings
    global user_counter

    id_read_from_form = -1
    user_counter += 1

    if not flask.current_app.scheduler_thread.isAlive():
        flask.current_app.scheduler_thread.start()

    if id_read_from_form == -1:
        id_for_hidden_thing = user_counter
    else:
        id_for_hidden_thing = id_read_from_form

    global_diagnostic_strings += "render_basic_whole_webpage() idrff="+str(id_read_from_form)+"<br>"

    return flask.render_template('bernardo.htm',
                                queue_size = flask.current_app.jobs_to_be_processed_queue.qsize(),
                                max_queue_size = flask.current_app.queue_MAXSIZE ,
                                being_processed = len(flask.current_app.active_processing_threads),
                                total = flask.current_app.job_processing_status_dict.get("num_jobs_completed",0),
                                start_time = flask.current_app.start_time,
                                distr = global_diagnostic_strings,
                                defid=id_for_hidden_thing)

@app.route("/begin_crunching",methods=["POST"])
def server_process_request_to_begin_crunching():
    global global_diagnostic_strings
    global id_read_from_form
    job_name = json.loads(request.data)["image_name"]
    print("request.data=",request.data)
    customer_id = json.loads(request.data)["CustId"]

    global_diagnostic_strings += "server_process_request_to_begin_crunching() "+str(customer_id)+"<br>"

    if (flask.current_app.jobs_to_be_processed_queue.qsize() >= flask.current_app.queue_MAXSIZE ):
        while(not flask.current_app.jobs_to_be_processed_queue.empty()):
            flask.current_app.jobs_to_be_processed_queue.get()

    requestedImage_status = {"name":job_name, "id":uuid.uuid1(), "diagstring": global_diagnostic_strings}

    flask.current_app.jobs_to_be_processed_queue.put(job_name)
    return flask.jsonify(requestedImage_status)

@app.route("/get_progress",methods=["POST"])
def server_asked_to_return_progress():
    global global_diagnostic_strings
	
    print(f'Current job being processed: {flask.current_app.job_processing_status_dict}')
    print(f'Current jobs completed: {flask.current_app.jobs_completed}')
    print("queue is: ",list(app.jobs_to_be_processed_queue.queue))
    image_name = json.loads(request.data)["image_name"]
    is_finished = flask.current_app.jobs_completed.get(image_name,{"status":0,"file": ''})["status"]
    customer_id = json.loads(request.data)["CustId"]
    global_diagnostic_strings += "server_asked_to_return_progress() in="+image_name+" cud="+str(customer_id)+" prog="+flask.current_app.job_processing_status_dict.get(image_name,"0")+"<br>"
    requestedImage_status = {
            "is_finished": is_finished,
            "progress":    flask.current_app.job_processing_status_dict.get(image_name,"0"),
            "diagstring": global_diagnostic_strings,
			"jobsaheadofus":app.jobs_to_be_processed_queue.qsize(),
			"inqueue":list(app.jobs_to_be_processed_queue.queue)
            }
    return flask.jsonify(requestedImage_status) #job_processing_status_dict[image_name]})

@app.route("/get_image",methods=["POST"])
def get_processed_image():
    global global_diagnostic_strings
    image_name = json.loads(request.data)["image_name"]
    customer_id = json.loads(request.data)["CustId"]
    file_bytes = flask.current_app.jobs_completed[image_name]["file"] #open("binary_image.jpeg", 'rb').read()
    file_bytes = base64.b64encode(file_bytes.getvalue()).decode()
    flask.current_app.jobs_completed.clear()
    global_diagnostic_strings += "get_processed_image() in="+image_name+" cud="+str(customer_id)+"<br>"
    return flask.jsonify({image_name:file_bytes,"diagstring": global_diagnostic_strings}) #job_processing_status_dict[image_name]})

if __name__ == '__main__':
    app.run(debug=True)