#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import requests
import smartsheet
import json
import os

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

# Spark's header with Token defined in environmental variables
spark_header = {
        'Authorization': 'Bearer ' + os.environ.get('SPARK_ACCESS_TOKEN', None),
        'Content-Type': 'application/json'
        }

# Message Received from Spark, because a WebHook has been configured to send
# messages to /webhook
@app.route('/webhook', methods=['POST','GET'])
def webhook():
    # Every message from Spark is received here.
    JSON = request.get_json(silent=True, force=True)
    # JSON is from Spark. This will contain the message, a personId, displayName,
    # and a personEmail that will be buffered for future use. sbuffer is a
    # dictionary as described on lines 40 to 41

    # Webhook is triggered if a message is sent to the bot. The JSON and the
    # message unciphered are then saved

    # First step is to discard bot's own messages
    if JSON['data']['personEmail'] != os.environ.get('BOT_EMAIL',
                                                                '@sparkbot.io'):
        roomId    = JSON['data']["roomId"]
        messageId = JSON['data']['id']
        # [Debug]
        #print("Message ID: \t" + messageId)

        # Message is not in the webhook. GET http request to Spark to obtain it
        message = requests.get(
                        url='https://api.ciscospark.com/v1/messages/'+messageId,
                    headers=spark_header)
        JSON = message.json()
        # Dictionary Containing info would be like this:
        # -------------------
        # !      roomId     |  Saving just in case
        # |message decrypted|  Used to compare with the message from api.ai
        # |    personId     |  Speaker unique ID
        # |   personEmail   |  Speaker unique email
        # |   displayName   |  Speaker´s displayed name
        # -------------------
        # Different ways of playing with JSON
        messagedecrypt  = JSON.get("text")
        personId        = JSON.get("personId")
        personEmail     = JSON.get("personEmail")
        # The Display Name of the person must be obtained from Spark too.
        # To get the displayName of the user, Spark only needs to know the
        # personId or the personEmail
        message = requests.get(
                        url='https://api.ciscospark.com/v1/people/'+personId,
                    headers=spark_header)
        JSON = message.json()
        displayName = JSON.get("displayName")
        # [Debug]
        #print ("Message Decrypted: "  + messagedecrypt
        #              + "\nroomId: \t"+ roomId
        #            + "\npersonId: \t"+ personId
        #          +"\npersonEmail: \t"+ personEmail
        #          +"\ndisplayName: \t"+ displayName
        # Save all in buffer for clarification
        sbuffer['roomId']     = roomId
        sbuffer['message']    = messagedecrypt
        sbuffer['personId']   = personId
        sbuffer['personEmail']= personEmail
        sbuffer['displayName']= displayName
        # [Debug]
        #print ("Buffer ACK")

        # Once this is done, we need to extract the command
        # Look how easy is to play with strings in Python!!:
        if "/search" in sbuffer["message"]:
            # Whe don´t need the word /search from the message
            query = sbuffer["message"].replace('/search', '')
            #[debug]
            print ("Asked to search " + query)
            sheetId = os.environ.get('SHEET_ID', None)
            # Now we search
            search_res = smartsheet.Search.search_sheet(sheetId, query)
            # Result is a smartsheet.models.SearchResult object.
            # Try - except for managing exceptions. If the following doesn´t
            # exists, we catch the exception, as it would mean we don´t have the
            # answer to the question
            try:
                rowId  = search_res.results[0].object_id
                # With the parameters needed to get the entire row, we request it
                row = smartsheet.Sheets.get_row(sheetId, rowId,
                            include='discussions,attachments,columns,columnType')
                # Answer is formatted in such a way that the cell where I know
                # where the data I want is in here:
                answer   = row.cells[1].value
                question = row.cells[0].value
            except:
                # If the before object doesn´t exists
                result = "Disculpe, no tenemos informacion de su pregunta " + query
                print('no result')
            else:
                result = "El Datasheet del dispositivo **" + question + "** esta [aqui](" + answer + ")"
        else:
            #If this command is not in the message, tell the user.
            result = "Disculpe " + displayName + ", no he identificado un \
            comando valido. Introduzca el comando /search"
            #[Debug]
            print(result)
        # Last thing is to send back the answer to the user. This will generate
        # a response to spark. Send in roomId received using markdown.
        r = requests.post('https://api.ciscospark.com/v1/messages',
                     headers=spark_header,
                        data=json.dumps({"roomId":sbuffer["roomId"],
                                       "markdown":result}))
        #[Debug]
        print("Code after send_message POST: "+str(r.status_code))
        status= "Message sent to Spark"
        if r.status_code !=200:
            print(str(json.loads(r.text)))
            if   r.status_code == 403:
                status= "Oops, no soy moderador del team de dicha sala"
            elif r.status_code == 404:
                status= "Disculpe. Ya no soy miembro ni moderador de dicho grupo"
            elif r.status_code == 409:
                status= "Lo siento, no ha podido ser enviado (409)"
            elif r.status_code == 500:
                status= "Perdón, los servidores de Spark están sufriendo \
                problemas. Compruébelo aquí: https://status.ciscospark.com/"
            elif r.status_code == 503:
                status= "Lo siento. Parece ser que los servidores de Spark no \
                pueden recibir mensajes ahora mismo"
            else:
                response = r.json()
                status= str("Error desconocido: "
                                        + response['errors'][0]['description'])
        #[Debug]
        print (status)
    else:
        # Message from bot must be ignored
        print ("message from bot: ignoring")
    return None

# App is listening to webhooks. Next line is used to executed code only if it is
# running as a script, and not as a module of another script.
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    #This will make your Flask app run with the following options. Debug
    # activates logs or verbose on the CLI where it is running
    app.run(debug=True, port=port, host='0.0.0.0', threaded=True)
