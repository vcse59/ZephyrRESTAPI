import sys
import socket
import threading
import Queue
import json
import base64
import requests
from time import gmtime
import datetime
import os
import time

SERVER_LISTEN_PORT          = 9999
CLIENT_CONNECTION_LIMIT     = 500
Queue_Container             = Queue.Queue()
USERNAME                    = <ZEPHYR_USERNAME>
PASSWORD                    = <ZEPHYR_PASSWORD>
CONTENT_TYPE                = "application/json"
exitFlag                    = False
threadList                  = []

class CRequestData:
    '''
    This class stores request data
    '''
    def __init__(self, pMethodType, pHttpURL, pDataPayload, connectionInfo, connectionSocket, socketStatus):
        '''
        Initialize class member variables
        :param self:
        :param pMethodType:
        :param pHttpURL:
        :param pDataPayload:
        :param pAddr:
        :return:
        '''
        self.m_methodType       = pMethodType
        self.m_httpURL          = pHttpURL
        self.m_dataPayload      = pDataPayload
        self.m_connectionInfo   = connectionInfo
        self.m_connectionSocket = connectionSocket
        self.socketStatus       = socketStatus

class CHttpClass:
    '''
    This class process http request get/post/put
    '''
    def __init__(self):
        '''
        Initializing class member variables in constructor
        '''
        self._httpSession                   = None
        self._userName                      = USERNAME
        self._password                      = PASSWORD
        self._contentType                   = CONTENT_TYPE
        self._encoded_login                 = base64.b64encode(b"%s:%s" %(self._userName, self._password))
        self._authorization                 = "Basic %s" %(self._encoded_login)

    def getHttpSession(self):
        '''
        Returns current http session[SINGLETON object]
        :return:
        '''
        try:
            if self._httpSession is None:
                self._httpSession = requests.session()
                self._httpSession.headers.update({"Authorization":"%s" %self._authorization, "Content-Type":"%s" %self._contentType })
            return self._httpSession
        except Exception as exp:
            print("Exception in CHttpClass::getHttpSession : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return None

    def get(self, requestURL):
        '''
        Process get http method
        :param requestURL:
        :return:
        '''
        try:
            print ("CHttpClass : get : %s" %requestURL)
            response = self.getHttpSession().get(requestURL, timeout=20)
            return response
        except Exception as exp:
            print("Exception in CHttpClass::get : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return None

    def put(self, putURL, values=None):
        '''
        Process put http method
        :param putURL:
        :param values:
        :return:
        '''
        try:
            print ("CHttpClass : put : %s & values : %s" %(putURL,values))
            response = self.getHttpSession().put(putURL, data = values, timeout=20)
            return response
        except Exception as exp:
            print("Exception in CHttpClass::put : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return None

    def post(self, postURL, values=None):
        '''
        Process post http method
        :param postURL:
        :param values:
        :return:
        '''
        try:
            print ("CHttpClass : post : %s & values : %s" %(postURL, values))
            response = self.getHttpSession().post(postURL, data=values, timeout=20)
            return response
        except Exception as exp:
            print("Exception in CHttpClass::post : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return None



class CProcessZephyrRequestThread (threading.Thread):
    '''
    This class is responsible for processing client request received and queued in shared queue by
    CReceiverZephyrRequestThread  and sending it's response
    back to associated clients
    '''
    def __init__(self, pthreadID, pthreadName):
        '''
        Initializing base class(thread) and class member variables
        :param pthreadID:
        :param pthreadName:
        '''
        threading.Thread.__init__(self)
        self.m_threadID           = pthreadID
        self.m_name               = pthreadName
        self.m_httpObj            = CHttpClass()

    def run(self):
        '''
        Thread callback function
        :return:
        '''
        global exitFlag

        try:
            print ("CProcessZephyrRequest: Starting " + self.m_name)
            while True:
                if exitFlag is False:
                    #print ("Queue : Length : %s" %Queue_Container.qsize())
                    if Queue_Container.empty() is False:
                        response = None
                        content = Queue_Container.get()

                        print ("CProcessZephyrRequest Data : " + ("None" if content.m_httpURL is None else content.m_httpURL))
                        print ("CProcessZephyrRequest  : %s %s %s" %(content.m_methodType , content.m_connectionInfo[0] , content.m_connectionInfo[1]))

                        if content.m_methodType == "GET":
                            response = self.m_httpObj.get(content.m_httpURL)
                        elif (content.m_methodType == "POST"):
                            response = self.m_httpObj.post(content.m_httpURL, None if (len(content.m_dataPayload) == 0) else (base64.b64decode(content.m_dataPayload)))
                        elif (content.m_methodType == "PUT"):
                            response = self.m_httpObj.put(content.m_httpURL, None if (len(content.m_dataPayload) == 0) else (base64.b64decode(content.m_dataPayload))) 
                        elif (content.m_methodType == "EXIT"):
                            print ("Closing TCP connection from %s on port number %s" %(content.m_connectionInfo[0], content.m_connectionInfo[1]))
                            content.socketStatus = False
                            continue
                        else:
                            print ("HTTP METHOD TYPE IS NOT VALID")
                        if response is None:
                            print ("No response for content.m_httpURL : %s" %content.m_httpURL)
                            continue
                        print ("Response: %s" %response.status_code)
                        if response.status_code == 200:
                            self.sendResponse(content.m_connectionInfo, content.m_connectionSocket, response.json(), response.status_code)
                        else:
                            self.sendResponse(content.m_connectionInfo, content.m_connectionSocket, None, response.status_code)
                else:
                    break
            print "CProcessZephyrRequest Exiting"
        except Exception as exp:
            print("Exception in CProcessZephyrRequest::run : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return

    def sendResponse(self, connectionInfo, connectionSocket, response, status_code):

        try:
            print ("Sending reponse to %s" %str(connectionInfo))

            msgLength = ""
            encodedMsg = ""
            if response is not None:
                responseData = json.dumps(response)
                #print (responseData)

                '''Encode the message using base64 encoding'''
                encodedMsg = base64.b64encode(responseData)
                msgLength = len(encodedMsg)
                print ("Sending %s to %s " %(len(encodedMsg), str(connectionInfo)))

            jsonData = {"len": str(msgLength), "payload": encodedMsg, "httpStatusCode": status_code}
            msg = json.dumps(jsonData)
            connectionSocket.send(msg + "#####")
        except Exception as exp:
            print("Exception in CProcessZephyrRequest::sendResponse : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            return 

class CTCPSocket:

    def __init__(self, pIPAddress, pPortNumber):

        self.mIPAddress         = pIPAddress
        self.mPortNumber        = pPortNumber
        self.sock               = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


        # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT state, without waiting for its natural timeout to expire
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.mIPAddress, self.mPortNumber))

        self.sock.listen(CLIENT_CONNECTION_LIMIT)

    def StartServerConnection(self, threadList):

        try:
            while True:
                connection, address = self.sock.accept()
                print ("Accepting connection from " + str(address))
                socketThread = ThreadDelegate(address, connection)
                socketThread.start()
                threadList.append(socketThread)
        except Exception as exp:
            print("Exception in CTCPSocket::StartServerConnection : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            for t in threadList:
                t.close()
            self.close()
            return 

    def close(self):
        self.sock.close()


class ThreadDelegate(threading.Thread):

    def __init__(self, connectionInfo, connectionSocket):

        threading.Thread.__init__(self)
        self.connectionInfo = connectionInfo
        self.connectionSocket = connectionSocket
        self.data = ""
        self.socketStatus = True

    def rchop(self, thestring, ending):
        if thestring.endswith(ending):
            return thestring[:-len(ending)]
        return thestring

    def run(self):

        try:

            completeData = ""
            while self.socketStatus is True:
                data = self.connectionSocket.recv(8096)
                if not data:
                    continue
                elif "####" in data:
                    dataString = self.rchop(data, "#####")
                    completeData = completeData + dataString
                    print ("+++++Complete Data : %s %s" %(completeData, len(completeData)))
                    self.insertParsedData(completeData)
                    completeData = ""
                elif data == "\"exit\"":
                    #self.parseSocketData(data)
                    self.insertParsedData("exit")
                    break
                elif "-exit" in data:
                    print ("ERROR : Invalid request")
                    break
                else:
                    completeData = completeData + data
                    print ("Data : %s %s" %(data, len(data)))
                    print ("++++In-Progress Data : %s %s" %(completeData, len(completeData)))

            print ("Thread execution completed successfully")
            self.close()
        except Exception as exp:
            print("Exception in ThreadDelegate::run : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            self.close()

    def parseSocketData(self, data):

        if "-" in data:
            splitData = data.split("-")
            print splitData
            if len(splitData) > 2:
                count = 0
                for count in range (0, len(splitData)):
                    print dataItem
                    if (self.data is None):
                        #pack the dataItem and insert in the queue
                        print self.data
                        #Queue_Container.put(dataItem)
                        self.insertParsedData(dataItem)
                        self.data = ""
                    else:
                        self.data = self.data + dataItem
                        #pack the dataItem and insert in the queue
                        print self.data
                        #Queue_Container.put(self.data)
                        self.insertParsedData(self.data)
                        self.data = ""
                self.data = self.data + splitData[len(splitData)]
            else:
                self.data = self.data + str(splitData[0])
                #Queue_Container.put(self.data)
                self.insertParsedData(self.data)
                self.data = str(splitData[1])
        else:
            self.data = self.data + data

    def insertParsedData(self, msg):

        print ("Parsed data: %s" %msg)

        try:
            if(msg == "exit"):
                print "Sending connection close message to Queue for processing"
                l_payload = CRequestData("EXIT", None, None, self.connectionInfo, self.connectionSocket, self.socketStatus)
            else:
                data = json.loads(msg)
                l_payload = CRequestData(data["method"], data["url"], data["data"], self.connectionInfo, self.connectionSocket, self.socketStatus)

            '''
            Queue the data for further processing by CProcessZephyrRequestThread
            '''
            Queue_Container.put(l_payload)
        except Exception as exp:
            print("Exception in ThreadDelegate::run : %s" %exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb.tb_lineno)
            self.connectionSocket.close()

    def printQueueData(self):

        if (Queue_Container.qsize() <= 0):
            print ("Data is Queue : %s" %(Queue_Container.qsize()))

    def close(self):
        self.connectionSocket.close()


class UserInput  (threading.Thread):
    '''
    This class is responsible for shutting down all the threads running in this python process
    '''
    def __init__(self, threadID, name):
        '''
        Initializing base class(thread) and class member variables
        :param threadID:
        :param name:
        '''
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name

    def run(self):
        '''
        Thread callback function
        :return:
        '''
        global exitFlag
        print "UserInput: Starting " + self.name

        while True:
            self.printQueueData()
            if exitFlag is False:
                if (os.path.isfile("./userInput.txt") is True):
                    fp = open("./userInput.txt", "r")
                    fileContent = fp.read()
                    fp.close()

                    if 'exit' in fileContent:
                        exitFlag = True
            else:
                break
            time.sleep(30)

    def printQueueData(self):

        if (Queue_Container.qsize() < 0):
            print ("=======================Queue Size : %s" %(Queue_Container.qsize()))
        #print ("=======================ThreadContainer Size : %s" %(len(threadList)))

def main():

    zephyrInterface = CProcessZephyrRequestThread(1234, "ZephyrProcess")
    thread3 = UserInput(5678, "User Input Thread")

    zephyrInterface.start()
    thread3.start()

    sockObj = CTCPSocket("127.0.0.1", SERVER_LISTEN_PORT)
    sockObj.StartServerConnection(threadList)

    threadList.append(zephyrInterface)
    threadList.append(thread3)
    for t in threadList:
        t.join()

    sockObj.close()

if __name__ == "__main__":
    main()
