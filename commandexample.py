#!/usr/bin/python
# -*- coding: UTF-8 -*-
################################################################################
#                             COMMANDEXAMPLE                                   #
#               https://yourdynoname.herokuapp.com:443/webhook                 #
# Flow:                                                                        #
# Spark--------------                                                          #
#                   |                                                          #
#                   --------->Dyno-------> External Sources:                   #
#                                                           smartsheet,        #
#                                                           Google,            #
#                                                           Spark,...          #
#                                                             |                #
#                                       -----------------------                #
#                                       |                                      #
#                            Dyno<------                                       #
#                              |                                               #
# Spark<-----------------------                                                #
################################################################################

# Please, take into account that lines identified as [Debug], like print(),
# indicates that this code purpose is debugging throught the CLI or logs console.
# They will not be presented anywhere else

import smartsheet
import time
import json
import os

import sdk
import spark

from flask import Flask
from flask import request
from flask import make_response

# Flask app should start in global layout
app = Flask(__name__)

# Instantiation of Smartsheet object
smartsheet = smartsheet.Smartsheet()

# Buffer for capturing messages from Spark
sbuffer = {"sessionId":"","roomId":"","message":"",
           "personId":"","personEmail":"","displayName":""}

# Defining user's dict
user    = {"personId":"","personEmail":"","displayName":""}

# Message Received from Spark
@app.route('/webhook', methods=['POST','GET'])
def webhook():
    # Speed meassuring variable
    start = time.time()
    # Every message from Spark is received here. I will be analyzed and sent to
    # api.ai response will then sent back to Spark
    req = request.get_json(silent=True, force=True)
    #print ('[Spark]')
    res = spark_webhook(req, start)
    #print (res)
    return None

def spark_webhook (req, start):
    # JSON is from Spark. This will contain the message, a personId, displayName,
    # and a personEmail that will be buffered for future use. sbuffer is a
    # dictionary as described on lines 44 to 46
    if sdk.buffer_it(req, sbuffer):
        # Once this is done, we need to extract the command
        # Look how easy is to play with strings in Python!!:
        if "/search" in sbuffer["message"]:
            #[debug]
            print ("Asked to search something")
            if sdk.get_user(req, sbuffer, user):
                result = sdk.search (smartsheet, user)
        else:
            #If this command is not in the message, tell the user.
            result="Disculpe, no he identificado un comando válido. Introduzca\
             el comando `/search`"
            #[Debug]
            print(result)
        # Last thing is to send back the answer to the user
        status = spark.bot_answer(
                            result,
                            sbuffer['file'],
                            None,
                            sbuffer['roomId'])
    else: status = "Error buffering"
    return status

# App is listening to webhooks. Next line is used to executed code only if it is
# running as a script, and not as a module of another script.
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print ("Starting app on port " +  str(port))
    #This will make your Flask app run with the following options. Debug
    # activates logs or verbose on the CLI where it is running
    app.run(debug=True, port=port, host='0.0.0.0', threaded=True)
