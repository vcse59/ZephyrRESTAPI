'''
Synopsis:
        This file provides the function to manage zephyr tool through REST APIs
'''
import base64, requests, os, sys
import json
import copy
import datetime
import re
import time
import ConfigParser
import random
import logging
import os
from time import gmtime
import socket
import threading


CONTENT_TYPE                    = "application/json"

USE_ZEPHYR_PROXY                = 0
ZEPHYR_PROXY_IP_ADDRESS         = "127.0.0.1"
ZEPHYR_PROXY_PORT_NUMBER        = 9999

#ZEPHYR_DATA_FILE_LOC            = "/var/www/zephyr_dashboard/ZephyrData/"
#ZEPHYR_CONFIG_PATH              = "/var/www/zephyr_dashboard/config.txt"

'''
Uncomment the below configuration to execute the script on mac
'''
ZEPHYR_DATA_FILE_LOC        = "./ZephyrData/"
ZEPHYR_CONFIG_PATH          = "config.txt"

#OPERATIONS
LIST_ALL_PROJECTS                   = "/project/"
LIST_ALL_RELEASES                   = "/release/project/PROJECTID"
GET_CYCLE_PHASE                     = "/cycle/release/RELEASEID"
CLONE_CYCLE                         = "/cycle/clone/CYCLEID?deep=DEEPFLAG&copyassignments=COPYASSIGN"
CREATE_CYCLE                        = "/cycle/"
CLONE_CYCLE_PHASE                   = "/cycle/cyclephase/clone/CYCLE_PHASE_ID"

CREATE_PHASE                        = "/cycle/CYCLE_ID/phase"
UPDATE_CYCLE_PHASE_VAL              = "/cycle/CYCLE_ID/phase"
GET_ALL_EXECUTION_BY_CRITERIA       = "/execution?testerid=TESTER_ID&cyclephaseid=CYCLE_PHASE_ID&releaseid=RELEASE_ID&pagesize=PAGE_SIZE"
GET_ALL_EXECUTION                   = "/execution?cyclephaseid=CYCLE_PHASE_ID&releaseid=RELEASE_ID&pagesize=PAGE_SIZE"
GET_COUNT_TESTCASES_BY_PHASE        = "/testcase/count?tcrcatalogtreeid=TCR_CATALOG_TREE_ID&releaseid=RELEASE_ID"
GET_ALL_EXECUTIONS                  = "/execution"
UPDATE_EXECUTION_RESULT             = "/execution/EXECUTION_ID?status=EXECUTION_RESULT&testerid=TESTER_ID&allExecutions=false"
UPDATE_TEST_STEP_RESULT             = "/execution/teststepresult/saveorupdate"
GET_USER_DETAILS                    = "/user/current"
GET_TEST_CASES_FOR_ASSIGN           = "/assignmenttree/testcase/CYCLE_PHASE_ID"
CHANGE_ASSIGNMENTS                  = "/assignmenttree/CYCLE_PHASE_ID/bulk/tree/TCR_CATALOG_TREE_ID/from/10/to/TESTER_ID?easmode=1"
GET_TEST_COUNT_BY_REL_ID            = "/testcase/count/RELEASE_ID"
GET_TEST_CASES_BY_TREEID            = "/testcase/tree/TREE_ID?pagesize=500"
GET_ASSIGNMENT_TREEID               = "/assignmenttree/CYCLE_PHASE_ID"
CREATE_PHASE_TEST_PLAN_BY_SEARCHID  = "/assignmenttree/CYCLE_PHASE_ID/assign/bysearch/ASSIGNMENT_TREE_ID?includehierarchy=true"
CREATE_PHASE_TEST_PLAN_BY_TREEID    = "/assignmenttree/CYCLE_PHASE_ID/assign/bytree/ASSIGNMENT_TREE_ID?includehierarchy=true"
FETCH_AUTOMATED_TEST_CASE           = "/advancesearch/?word=tag%20%3D%20%22automated%22&firstresult=0&maxresults=500&entitytype=testcase&zql=true&releaseid=RELEASE_ID&projectid=PROJECT_ID"
FETCH_TEST_CASE_STEPS               = "/testcase/TEST_CASE_ZEPHYR_ID/teststep?isfetchstepversion=IS_FETCH_VERSION&versionId=TEST_CASE_VERION_ID"
FETCH_ALL_TEST_CASE                 = "/testcasetree?type=Phase&releaseid=RELEASE_ID"

ZEPHYR_TEST_REPO_PATH = { "CLIENT_INTEGRATION_SMOKE" : "Automation Tests:Client Integration Tests:Smoke Tests",
                          "SYSTEM_SMOKE" : "Automation Tests:System Tests:Smoke Tests"}

#test case status enumeration
TEST_CASE_STATUS_MAPPINGS = { "PASSED" : 1, "FAILED" : 2, "WIP":   3, "BLOCK":  4}

#Initializing log handler
logger = None

def add_zephyr_log_handler(log_dir, loghandler=None):
    """
    This function set the logging directory and add logging handler.
    """
    global logger

    if loghandler is None:
        logger = logging.getLogger("nulllog")
        formt = logging.Formatter("%(levelname)s %(asctime)s %(funcName)s \
          %(lineno)d %(message)s")
        formt.converter = gmtime

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        #get the file handler
        dateTag = datetime.datetime.utcnow().strftime("%b-%d_%H-%M-%S")
        FILE_NAME = "zephyr_module_" + dateTag + ".logger"
        LOG_FILE = os.path.join(log_dir, FILE_NAME)
        handl = logging.FileHandler(LOG_FILE)
        handl.setFormatter(formt)

        logger.addHandler(handl)
        logger.setLevel(logging.DEBUG)
    else:
        logger  = loghandler

def sendLogToStdout(logMessage):
    dateTag = datetime.datetime.now()
    print('%s : %s' %(dateTag, logMessage))

class CfgReader(object):
    '''
    This class read config file in below given format.
    [section1]
    param1=val1

    [section2]
    param1=val1
    '''
    def __init__(self, cfg_file=None):
        '''
        Construct a new CfgReader object
        Args:
            cfg_file: Absolute pathe of config file.
        '''
        self.cfg = cfg_file
        self.config = ConfigParser.ConfigParser()
        if self.cfg:
            self.config.read(self.cfg)

    def get_config_param(self, section, param):
        '''
        Get the config param in str
        Args:
            section: section of the config file from which param will be fetched
            param: parameter name which will be fetched

        Returns:
            str - value of config param in str
            None - if param or section not present in config file
        '''
        if section in self.config.sections():
            try:
                val = self.config.get(section, param)
                return val
            except:
                sendLogToStdout("Config section=%s doesn't contain %s param" %(section, param))
                return None
        else:
            return None

#################################################UserID information#####################################################################

class CUserRoles:
    '''
    This class stores user role parameters
    '''
    def __init__(self, id, name, description, hasManagerApp):
        '''
        Initializing variables in constructor
        :param id:                  User Identifier
        :param name:                User name
        :param description:         User description
        :param hasManagerApp:       User role
        '''
        self.id                 = id
        self.name               = name
        self.description        = description
        self.hasManagerApp      = hasManagerApp

class CUserGroups:
    '''
    This class stores user group parameters
    '''
    def __init__(self, id, name, editable, disabled, canCreate, canAssign, canChangeState, createdOn):
        '''
        Initializing member variables in constructor
        :param id:              Group ID
        :param name:            Group name
        :param editable:        Group editable flag
        :param disabled:        Group disabled flag
        :param canCreate:       Create flag
        :param canAssign:       Assign flag
        :param canChangeState:  Change state flag
        :param createdOn:       Group created on date
        '''
        self.id             = id
        self.name           = name
        self.editable       = editable
        self.disabled       = disabled
        self.canCreate      = canCreate
        self.canAssign      = canAssign
        self.canChangeState = canChangeState
        self.createdOn      = createdOn

class CUserInfo:
    '''
    This class stores user information parameters
    '''
    def __init__(self, id, username, firstName, lastName, location, type, email,
                 accountEnabled, accountExpired, credentialsExpired, loginName,
                 rolesListObj, userType, chargeableFlag, lastSuccessfulLogin, lastSuccessfulLoginString,
                 groupsListObj, fullName):
        '''
        Initializing class member variables in constructor
        :param id:                              User Identifier
        :param username:                        User name
        :param firstName:                       First name of user
        :param lastName:                        Last name of user
        :param location:                        User location
        :param type:                            User type
        :param email:                           User email ID
        :param accountEnabled:                  User account enable/disable flag
        :param accountExpired:                  User account expired flag
        :param credentialsExpired:              User credentials expiry flag
        :param loginName:                       User login name
        :param rolesListObj:                    User roles
        :param userType:                        Role type of  user
        :param chargeableFlag:                  chargeable flag
        :param lastSuccessfulLogin:             Last successful login
        :param lastSuccessfulLoginString:       Login string of last successful login
        :param groupsListObj:                   Role type of Group
        :param fullName:                        User full name
        '''
        self.id                         = id
        self.username                    = username
        self.firstName                  = firstName
        self.lastName                   = lastName
        self.location                   = location
        self.type                       = type
        self.email                      = email
        self.accountEnabled             = accountEnabled
        self.accountExpired             = accountExpired
        self.credentialsExpired         = credentialsExpired
        self.loginName                  = loginName
        self.rolesListObj               = rolesListObj
        self.userType                   = userType
        self.chargeableFlag             = chargeableFlag
        self.lastSuccessfulLogin        = lastSuccessfulLogin
        self.lastSuccessfulLoginString  = lastSuccessfulLoginString
        self.groupsListObj              = groupsListObj
        self.fullName                   = fullName

########################################################################################################################################

class CProjectDetail:
    '''
    This class store Project detail variables values
    '''
    def __init__(self, id, version, name, desc, startDate, projectStartDate, status,
                 showItem, newItem, members, isolationLevel, dashboardSecured, dashboardURL,
                 dashboardRestricted, createdOn, shared):
        '''
        Initializing class member variables in constructor
        :param id:                          project identifier
        :param version:                     project version
        :param name:                        project name
        :param desc:                        project description
        :param startDate:                   project start date
        :param projectStartDate:            project start date
        :param status:                      project status
        :param showItem:                    Item to show in an project
        :param newItem:                     new Item in an project
        :param members:                     project members
        :param isolationLevel:              isolate level
        :param dashboardSecured:            secured Dashboard
        :param dashboardURL:                dashboard URL
        :param dashboardRestricted:         restriction on Dashboard
        :param createdOn:                   creation date of project
        :param shared:                      shared flag of project
        '''
        self.id                     = id
        self.version                = version
        self.name                   = name
        self.desc                   = desc
        self.startDate              = startDate
        self.projectStartDate       = projectStartDate
        self.status                 = status
        self.showItem               = showItem
        self.newItem                = newItem
        self.members                = members
        self.isolationLevel         = isolationLevel
        self.dashboardSecured       = dashboardSecured
        self.dashboardURL           = dashboardURL
        self.dashboardRestricted    = dashboardRestricted
        self.createdOn              = createdOn
        self.shared                 = shared

class CReleaseDetail:
    '''
    This class stores release job variable values configured in current selected project
    '''
    def __init__(self, id, name, desc, startDate, releaseStartDate, endDate,
                 releaseEndDate, createdDate, status, externalSystem, projectId, orderID):
        '''
        Initializing class member variables in constructor
        :param id:                          release identifier
        :param name:                        release name
        :param desc:                        release description
        :param startDate:                   release start date
        :param releaseStartDate:            release start date
        :param endDate:                     release end date
        :param releaseEndDate:              release end date
        :param createdDate:                 release creation date
        :param status:                      release status
        :param externalSystem:              release external system
        :param projectId:                   project identifier
        :param orderID:                     release order identifier
        '''
        self.id                     = id
        self.name                   = name
        self.desc                   = desc
        self.startDate              = startDate
        self.releaseStartDate       = releaseStartDate
        self.endDate                = endDate
        self.releaseEndDate         = releaseEndDate
        self.createdDate            = createdDate
        self.status                 = status
        self.externalSystem         = externalSystem
        self.projectId              = projectId
        self.orderID                = orderID

class AutomationCycleDetail:
    '''
    This class stores variable values for cycle planned in a release
    '''
    def __init__(self, id, environment, build, name, startDate, endDate,
                 cycleStartDate, cycleEndDate, status, revision, releaseId,
                 cyclePhases, createdOn):
        '''
        Initializing class member variables in constructor
        :param id:                  cycle identifier
        :param environment:         environment details
        :param build:               build details
        :param name:                cycle name
        :param startDate:           cycle start date
        :param endDate:             cycle end date
        :param cycleStartDate:      cycle start date
        :param cycleEndDate:        cycle end date
        :param status:              cycle status
        :param revision:            cycle revision number
        :param releaseId:           release identifier
        :param cyclePhases:         list of cycle phases
        :param createdOn:           creation date of cycle
        '''
        self.id             = id
        self.environment    = environment
        self.build          = build
        self.name           = name
        self.startDate      = startDate
        self.endDate        = endDate
        self.cycleStartDate = cycleStartDate
        self.cycleEndDate   = cycleEndDate
        self.status         = status
        self.revision       = revision
        self.releaseId      = releaseId
        self.cyclePhases    = cyclePhases
        self.createdOn      = createdOn

class AutomationCyclePhase:
    '''
    This class stores phase variables values for currently selected cycle
    '''
    def __init__(self, id, name, tcrCatalogTreeId, freeForm,
                 startDate, endDate, createdOn, cycleId, phaseStartDate,
                 phaseEndDate):
        '''
        Initializing class member variables in constructor
        :param id:                  cycle phase identifier
        :param name:                cycle phase name
        :param tcrCatalogTreeId:    cycle phase tcr Catalog tree identifier
        :param freeForm:            cycle phase free form flag
        :param startDate:           cycle phase start date
        :param endDate:             cycle phase end date
        :param createdOn:           creation date of cycle phase
        :param cycleId:             cycle identifier
        :param phaseStartDate:      cycle phase start date
        :param phaseEndDate:        cycle phase end date
        '''
        self.id                 = id
        self.name               = name
        self.tcrCatalogTreeId   = tcrCatalogTreeId
        self.freeForm           = freeForm
        self.startDate          = startDate
        self.endDate            = endDate
        self.createdOn          = createdOn
        self.cycleId            = cycleId
        self.phaseStartDate     = phaseStartDate
        self.phaseEndDate       = phaseEndDate

    def GetJSONPayload(self):
        '''
        This function form JSON payload of variable require to create new cycle phase
        :return:    JSON payload
        '''
        dictValues = {}
        dictValues["id"]                = self.id
        dictValues["name"]              = self.name
        dictValues["tcrCatalogTreeId"]  = self.tcrCatalogTreeId
        dictValues["freeForm"]          = self.freeForm
        dictValues["startDate"]         = self.startDate
        dictValues["endDate"]           = self.endDate
        dictValues["createdOn"]         = self.createdOn
        dictValues["cycleId"]           = self.cycleId
        dictValues["phaseStartDate"]    = self.phaseStartDate
        dictValues["phaseEndDate"]      = self.phaseEndDate

        listValue = []
        listValue.append(dictValues)
        return listValue

    def GetJSONPayloadForUpdation(self, newCyclePhaseName, startDate, endDate, createdOn):
        '''
        Return JSON payload to update Cycle Phase Values
        :param newCyclePhaseName:       cycle phase name
        :param startDate:               cycle start date
        :param endDate:                 cycle end date
        :param createdOn:               creation date of cycle
        :return:    JSON payload
        '''
        values = json.dumps({"id": self.id, "name": newCyclePhaseName, "tcrCatalogTreeId": self.tcrCatalogTreeId,
                                "freeForm": self.freeForm, "startDate": startDate, "endDate": endDate,
                                "createdOn": createdOn, "cycleId": self.cycleId})
        return values

class CreateNewCycle:
    '''
    This class encapsulate variable values require to create new cycle
    '''
    def __init__(self, cloneCycleId, environment, build, name, startDate, endDate, cycleStartDate
                 , cycleEndDate, status, revision, releaseId, cyclePhases, createdOn, releaseName
                 , projectName, projectId):
        '''
        Initializing class member variables in constructor
        :param cloneCycleId:        cycle identifier
        :param environment:         environment details
        :param build:               build details
        :param name:                cycle name
        :param startDate:           cycle start date
        :param endDate:             cycle end date
        :param cycleStartDate:      cycle start date
        :param cycleEndDate:        cycle end date
        :param status:              cycle status
        :param revision:            cycle revision number
        :param releaseId:           release indentifier
        :param cyclePhases:         list of cycle phases
        :param createdOn:           creation date of cycle
        :param releaseName:         release name
        :param projectName:         project name
        :param projectId:           project identifier
        '''
        self.id                 = cloneCycleId
        self.environment        = environment
        self.build              = build
        self.name               = name
        self.startDate          = startDate
        self.endDate            = endDate
        self.cycleStartDate     = cycleStartDate
        self.cycleEndDate       = cycleEndDate
        self.status             = status
        self.revision           = revision
        self.releaseId          = releaseId
        self.cyclePhases        = cyclePhases
        self.createdOn          = createdOn
        self.releaseName        = releaseName
        self.projectName        = projectName
        self.projectId          = projectId

    def GetJSONPayload(self):
        '''
        This function form JSON payload of variable require to create new cycle
        :return value in json format:
        '''
        values =  json.dumps({"id": self.id, "environment":self.environment, "build": self.build, "name":self.name
                             ,"startDate":self.startDate, "endDate":self.endDate, "cycleStartDate":self.cycleStartDate
                             ,"cycleEndDate":self.cycleEndDate, "status":self.status, "revision":self.revision
                             ,"releaseId": self.releaseId, "cyclePhases":self.cyclePhases, "createdOn":self.createdOn
                             ,"releaseName":self.releaseName, "projectName":self.projectName, "projectId": self.projectId})
        return values

class CTestCase:
    '''
    This class stores test case variables values
    '''


    def __init__(self, lastModifiedOn, versionCreationDate, requirementIds, customFieldProcessed,
                 tag, requirementIdsNew, tcCreationData, customProperties,
                 id, description, estimatedTime, projectId, testcaseType,
                 automationDefault, comments, priority, externalId, oldId, lastUpdaterId,
                 isComplex, testcaseSequence, projectName, testcaseid, customProcessedProperties,
                 versionNumber, automated, creationDate, name, customFieldValueListObj, creatorId,
                 testcaseShared, versionCreatedBy):

        self.lastModifiedOn                     = lastModifiedOn
        self.versionCreationDate                = versionCreationDate
        self.requirementIds                     = requirementIds
        self.customFieldProcessed               = customFieldProcessed
        self.tag                                = tag
        self.requirementIdsNew                  = requirementIdsNew
        self.tcCreationData                     = tcCreationData
        self.customProperties                   = customProperties
        self.id                                 = id
        self.description                        = description
        self.estimatedTime                      = estimatedTime
        self.projectId                          = projectId
        self.testcaseType                       = testcaseType
        self.automationDefault                  = automationDefault
        self.comments                           = comments
        self.priority                           = priority
        self.externalId                         = externalId
        self.oldId                              = oldId
        self.lastUpdaterId                      = lastUpdaterId
        self.isComplex                          = isComplex
        self.testcaseSequence                   = testcaseSequence
        self.projectName                        = projectName
        self.testcaseid                         = testcaseid
        self.customProcessedProperties          = customProcessedProperties
        self.versionNumber                      = versionNumber
        self.automated                          = automated
        self.creationDate                       = creationDate
        self.name                               = name
        self.customFieldValueListObj            = customFieldValueListObj
        self.creatorId                          = creatorId
        self.testcaseShared                     = testcaseShared
        self.versionCreatedBy                   = versionCreatedBy

class CTestCaseCustomFieldValue:

    def __init__(self, displayName, value, testcaseVersionId, pickListValue,
                 fieldName, fieldTypeMetadata, fieldId, id):

        self.displayName            = displayName
        self.value                  = value
        self.testcaseVersionId      = testcaseVersionId
        self.pickListValue          = pickListValue
        self.fieldName              = fieldName
        self.fieldTypeMetadata      = fieldTypeMetadata
        self.fieldId                = fieldId
        self.id                     = id

class CTestCaseVersion:
    '''
    This class stores test case version variables values
    '''
    def __init__(self, customProperties, customProcessedProperties, id, name, description,
                 tag, lastModifiedOn, creationDate, tcCreationDate, comments, isComplex,
                 estimatedTime, creatorId, lastUpdaterId, oldId, automated,
                 scriptName, releaseId, customFieldProcessed, customFieldValues,
                 testcaseId,versionNumber, projectId, versionCreatedBy, versionCreationDate,
                 sourceTestcaseId, sourceTestcaseVersionNumber,automatedDefault):
        '''
        Initializing class member variables in constructor
        :param customProperties:            custom test case properties
        :param customProcessedProperties:   custom test case properties
        :param id:                          test case identifier
        :param name:                        test case name
        :param description:                 test case description
        :param tag:                         test case tag
        :param lastModifiedOn:
        :param creationDate:
        :param tcCreationDate:
        :param comments:
        :param isComplex:
        :param estimatedTime:
        :param creatorId:
        :param lastUpdaterId:
        :param oldId:
        :param automated:
        :param scriptName:
        :param releaseId:
        :param customFieldProcessed:
        :param customFieldValues:
        :param testcaseId:
        :param versionNumber:
        :param projectId:
        :param versionCreatedBy:
        :param versionCreationDate:
        :param sourceTestcaseId:
        :param sourceTestcaseVersionNumber:
        :param automatedDefault:
        '''
        self.customProperties                   = customProperties
        self.customProcessedProperties          = customProcessedProperties
        self.id                                 = id
        self.name                               = name
        self.description                        = description
        self.tag                                = tag
        self.lastModifiedOn                     = lastModifiedOn
        self.creationDate                       = creationDate
        self.tcCreationDate                     = tcCreationDate
        self.comments                           = comments
        self.isComplex                          = isComplex
        self.estimatedTime                      = estimatedTime
        self.creatorId                          = creatorId
        self.lastUpdaterId                      = lastUpdaterId
        self.oldId                              = oldId
        self.automated                          = automated
        self.scriptName                         = scriptName
        self.releaseId                          = releaseId
        self.customFieldProcessed               = customFieldProcessed
        self.customFieldValues                  = customFieldValues
        self.testcaseId                         = testcaseId
        self.versionNumber                      = versionNumber
        self.projectId                          = projectId
        self.versionCreatedBy                   = versionCreatedBy
        self.versionCreationDate                = versionCreationDate
        self.sourceTestcaseId                   = sourceTestcaseId
        self.sourceTestcaseVersionNumber        = sourceTestcaseVersionNumber
        self.automationDefault                  = automatedDefault

class CTcrTreeTestCase:
    '''
    This class stores Test Case tree variable values
    '''
    def __init__(self, lastModifiedOn, releaseName, stateFlag, projectIdParam, tcrCatalogTreeId,
                 projectId, orderId, original, testcaseObj, releaseId, versionNumber, isDerivedFromBDD,
                 maxVersionNumber, id, revision):
        '''
        Initializing class member variables in constructor
        :param id:
        :param tcrCatalogTreeId:
        :param testcaseObj:
        :param revision:
        :param stateFlag:
        :param lastModifiedOn:
        :param versionNumber:
        :param testcaseVersionObj:
        :param original:
        '''

        self.lastModifiedOn         = lastModifiedOn
        self.releaseName            = releaseName
        self.stateFlag              = stateFlag
        self.projectIdParam         = projectIdParam
        self.tcrCatalogTreeId       = tcrCatalogTreeId
        self.projectId              = projectId
        self.projectIdParam         = projectIdParam
        self.orderId                = orderId
        self.original               = original
        self.testcaseObj            = testcaseObj
        self.releaseId              = releaseId
        self.versionNumber          = versionNumber
        self.isDerivedFromBDD       = isDerivedFromBDD
        self.maxVersionNumber       = maxVersionNumber
        self.id                     = id
        self.revision               = revision

class CTestSteps:
    '''
    This class stores test steps
    '''

    def __init__(self, id, localId, orderId, step, data, result):
        '''
        :param id:
        :param localId:
        :param orderId:
        :param step:
        :param data:
        :param result:
        '''

        self.id                         = id
        self.localId                    = localId
        self.orderId                    = orderId
        self.step                       = step
        self.data                       = data
        self.result                     = result

class CTestCaseExecutionInfo:
    '''
    This class stores Test case execution information including test steps
    '''

    def __init__(self, id, tcId, releaseId, maxId, stepsObj, lastModificationDate, lastModifiedBy):
        '''
        :param id:
        :param tcId:
        :param releaseId:
        :param maxId:
        :param stepsObj:
        :param lastModificationData:
        :param lastModifiedBy:
        '''

        self.id                         = id
        self.tcId                       = tcId
        self.releaseId                  = releaseId
        self.maxId                      = maxId
        self.steps                      = stepsObj
        self.lastModificationDate       = lastModificationDate
        self.lastModifiedBy             = lastModifiedBy

class CLastTestResult:
    '''
    This class stores execution detail of last test case executed by releaseTestScheduleId
    '''
    def __init__(self, id, executionDate, execDate, executionStatus, testerId, releaseTestScheduleId):
        '''
        Initializing class member variables in constructor
        :param id:
        :param executionDate:
        :param execDate:
        :param executionStatus:
        :param testerId:
        :param releaseTestScheduleId:
        '''
        self.id                         = id
        self.executionDate              = executionDate
        self.execDate                   = execDate
        self.executionStatus            = executionStatus
        self.testerId                   = testerId
        self.releaseTestScheduledId     = releaseTestScheduleId

class CExecutionDetail:
    '''
    This class stores execution details corresponds to releaseTestScheduleId
    '''
    def __init__(self, status, lastModifiedOn, attachementCount, tcrTreeTestCaseObj, testerId,
                 defectList, assignmentDate, cyclePhaseId, id, testStepObj, lastTestResultObj = None, versionId = None,
                 executedBy = None, actualTime = None):
        '''
        Initializing class member variables in constructor
        :param id:
        :param actualTime:
        :param versionId:
        :param testerId:
        :param executedBy:
        :param tcrTreeTestcaseObj:
        :param cyclePhaseId:
        :param lastTestResultObj:
        :param defects:
        :param attachmentCount:
        :param lastModifiedOn:
        '''
        self.status                     = status
        self.lastModifiedOn             = lastModifiedOn
        self.attachementCount           = attachementCount
        self.tcrTreeTestCaseObj         = tcrTreeTestCaseObj
        self.testerId                   = testerId
        self.defectList                 = defectList
        self.assignmentDate             = assignmentDate
        self.cyclePhaseId               = cyclePhaseId
        self.id                         = id
        self.testStepObj                =  testStepObj
        self.lastTestResultObj          = lastTestResultObj
        self.versionId                  = versionId
        self.executedBy                 = executedBy
        self.actualTime                 = actualTime

class CDefectDetail:
    '''
    This class stores defect details corresponds to failed test cases
    '''
    def __init__(self, id, bugId, externalId, description, createdDate, status,
                 priority, state, dtsId, category, testResults):
        '''
        Initializing class member variables in constructor
        :param id:
        :param bugId:
        :param externalId:
        :param description:
        :param createdDate:
        :param status:
        :param priority:
        :param state:
        :param dtsId:
        :param category:
        :param testResults:
        '''
        self.id                 = id
        self.bugId              = bugId
        self.externalId         = externalId
        self.description        = description
        self.createdDate        = createdDate
        self.status             = status
        self.priority           = priority
        self.state              = state
        self.dtsId              = dtsId
        self.category           = category
        self.testResults        = testResults

###########################################Cycle Phase Assignment Tree############################################################################################

class CPhaseTreeAssignmentInfo:

    def __init__(self, id, type, name, description, revision, categoriesList, assignedUsersList, releaseId,
                 linkedTCRCatalogTreeId, createdOn, lastModifiedOn):

        self.id                     = id
        self.type                   = type
        self.name                   = name
        self.description            = description
        self.revision               = revision
        self.categories             = categoriesList
        self.assignedUsers          = assignedUsersList
        self.releaseId              = releaseId
        self.linkedTCRCatalogTreeId = linkedTCRCatalogTreeId
        self.createdOn              = createdOn
        self.lastModifiedOn         = lastModifiedOn

###########################################ZEPHYR CLASS TO CAPTURE COMPLETE PROJECT INFO##########################################################################


class CReleaseInfo:
    '''
    This class stores release cycle details
    '''
    def __init__(self, releaseDetail):
        '''
        Initializing class member variables in constructor
        :param releaseDetail:
        '''
        self.releaseCycle         =   None
        self.releaseInfo         = releaseDetail

    def updateReleaseCycleInfo(self, releaseCycleInfo):
        '''
        Updates class member variable with release cycle information
        :param releaseCycleInfo:
        :return:
        '''
        self.releaseCycle   = releaseCycleInfo

class CProjectInfo:
    '''
    This class stores project release information
    '''

    def __init__(self, projectDetail):
        '''
        Initializing class member variables in constructor
        :param projectDetail:
        '''
        self.projectInfo        = projectDetail
        self.releaseListDetail  = []

    def appendReleaseInfo(self, releaseDetail, releaseCycleInfo):
        '''
        Append release information to class member variable self.releaseListDetail
        :param releaseDetail:
        :param releaseCycleInfo:
        :return:
        '''
        relTemp = None

        '''
        Iterate over the saved release list to check if release exists
        '''
        for relItem in self.releaseListDetail:
            if relItem.releaseInfo.id == releaseDetail.id:
                relTemp = relItem
                break

        if relTemp is None:
            '''
            Append the release information to member variable
            '''
            relTemp = CReleaseInfo(releaseDetail)
            self.releaseListDetail.append(relTemp)

        '''
        Update the cycle information in associated CReleaseInfo Class object
        '''
        relTemp.updateReleaseCycleInfo(releaseCycleInfo)

class CZephyrProjectInfo:

    def __init__(self, projectDetail, releaseDetail, releaseCycleInfo):

        self.projectList        = []
        self.appendProjectInfo(projectDetail, releaseDetail, releaseCycleInfo)

    def appendProjectInfo(self, projectDetail, releaseDetail, releaseCycleInfo):

        projTemp    = None

        for projItem in self.projectList:
            if projItem.projectInfo.id == projectDetail.id:
                projTemp   = projItem
                break

        if projTemp is None:
            projTemp      = CProjectInfo(projectDetail)
            self.projectList.append(projTemp)

        projTemp.appendReleaseInfo(releaseDetail, releaseCycleInfo)

###########################################ZePHYR METRIC CLASS##############################################################################################
class CZephyrCyclePhaseMetric:

    def __init__(self, passedCount, failedCount, blockedCount, WipCount, newDefectCount, existingDefectCount, totalTestCases):

        self.passedCount            = passedCount
        self.failedCount            = failedCount
        self.blockedCount           = blockedCount
        self.WipCount               = WipCount
        self.newDefectCount         = newDefectCount
        self.existingDefectCount    = existingDefectCount
        self.TotalTestCases         = totalTestCases

###########################################ZEPHYR CLASS TO CAPTURE COMPLETE TEST REPO INFO##########################################################################
class CTestRepositoryTestCaseInfo:

    def __init__(self):

        self.testRepoTestCaseInfo = []

    def append(self, testCaseDetailObj):
        self.testRepoTestCaseInfo.append(testCaseDetailObj)

    def count(self):
        return len(self.testRepoTestCaseInfo)

    def StripListValues(self, listContainer):

        tagNameList = []

        for item in listContainer:
            tagNameList.append(str(item).strip())

        return tagNameList

    def countByTags(self, tagName):

        taggedTestCase = 0
        testCaseList = []

        for testCase in self.testRepoTestCaseInfo:
            CommaSeperatedItem = str(testCase.testcaseObj.tag).split(",")
            SpaceSeperatedItem = str(testCase.testcaseObj.tag).split(" ")

            tagListByComma = self.StripListValues(CommaSeperatedItem)
            tagListBySpace = self.StripListValues(SpaceSeperatedItem)

            #Convert list of python string to lowercase
            tagListByComma = [x.lower() for x in tagListByComma]
            tagListBySpace = [x.lower() for x in tagListBySpace]

            if (tagName.lower() in tagListByComma):
                taggedTestCase = taggedTestCase + 1
                testCaseList.append(testCase)
            elif (tagName.lower() in tagListBySpace):
                taggedTestCase = taggedTestCase + 1
                testCaseList.append(testCase)

        return testCaseList, taggedTestCase


############################################CUDP CLASS#################################################################################

class CResponseObject:

    def __init__(self, responseData, httpResponse):

        self.status_code            = httpResponse
        self._json                  = responseData

    def json(self):

        return self._json

class CUDPSocketClass:

    def __init__(self, dest_ip, dest_port):

        self._dest_ip                       = dest_ip
        self._dest_port                     = dest_port
        self._sock                          = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udpSession                    = None
        self._sock.settimeout(30)

    def processUDPRequest(self, requestObject):

        self._sock.sendto(requestObject.GetJSONPayload(), (self._dest_ip, self._dest_port))
        payloadLength         = 0
        CompleteZephyrResponseLength = 0
        payload = ""
        decodedMessgae = ""
        status_code = 0

        while (True):
            data, addr = self._sock.recvfrom(8092)
            jsonData = json.loads(data)
            CompleteZephyrResponseLength = int(jsonData["len"])
            payload = payload + str(jsonData["payload"])
            payloadLength = len(payload)
            status_code = int(jsonData["httpStatusCode"])


            if payloadLength == CompleteZephyrResponseLength:
                break
        if payloadLength > 0:
            decodedMessgae  = json.loads(base64.decodestring(payload))
        sendLogToStdout("Zephyr Response for GET request is : %s and response message is : %s" %(status_code, decodedMessgae))

        responseObject = CResponseObject(decodedMessgae, status_code)

        return responseObject

class CTCPSocketClass:

    def __init__(self, pIPAddress, pPortNumber):
        self.mIPAddress = pIPAddress
        self.mPortNumber = pPortNumber
        self.mData = ''
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.mIPAddress, self.mPortNumber))

    def processTCPRequest(self, requestObject):

        try:
            self.sock.send(requestObject.GetJSONPayload() + "#####")
            sendLogToStdout("Sending (%s) to : %s" %(requestObject.GetJSONPayload(), self.sock.getsockname()))
            recvData = self.recvSocketData()
            sendLogToStdout("Response Data : %s" % recvData)

            jsonData = json.loads(recvData)
            CompleteZephyrResponseLength = int(jsonData["len"])
            payload = str(jsonData["payload"])
            payloadLength = len(payload)
            status_code = int(jsonData["httpStatusCode"])

            decodedMessgae = json.loads(base64.decodestring(payload))

            sendLogToStdout(
                    "Zephyr Response for GET request is : %s and response message is : %s" % (
            status_code, decodedMessgae))

            responseObject = CResponseObject(decodedMessgae, status_code)

            return responseObject
        except Exception as exp:
            sendLogToStdout("Exception in CTCPSocketClass::processTCPRequest : %s " % exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            sendLogToStdout("%s %s %s" %(exc_type, exc_obj, exc_tb.tb_lineno))
            return None



    def recvSocketData(self):

        lResponseData = ""
        try:
            while True:
                self.sock.settimeout(120)

                recvData = self.sock.recv(1048576)

                #sendLogToStdout("++++Socket recvData : %s" %(recvData))
                #sendLogToStdout("############self.mData : %s LEN: %s" % (self.mData, len(self.mData)))
                #sendLogToStdout("############lResponseData : %s LEN: %s" % (lResponseData, len(lResponseData)))

                # Add the socket data to mData
                self.mData = self.mData + recvData

                if len(self.mData) == 0:
                    continue
                elif '#####' in self.mData:
                    #socket data end with -exit
                    lResponseData = self.mData.split("#####")[0]
                    remainingSocketDataList = self.mData.split("#####")[1:]
                    self.mData = "#####".join(remainingSocketDataList)
                    break
                elif recvData == "EXIT":
                    lResponseData = recvData
                    break
                else:
                    continue

            return lResponseData
        except socket.timeout as timeoutExp:
            sendLogToStdout("Timeout in CTCPSocketClass::recvSocketData : %s " % lResponseData)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            sendLogToStdout("%s %s %s" %(exc_type, exc_obj, exc_tb.tb_lineno))

            sendLogToStdout("=========self.mData : %s LEN: %s" % (self.mData, len(self.mData)))
            sendLogToStdout("=========lResponseData : %s LEN: %s" % (lResponseData, len(lResponseData)))
            data = lResponseData
            if lResponseData[-4:] == "####":
                data = lResponseData.split("-")[0]
            return data
        except Exception as exp:
            sendLogToStdout("Exception in CTCPSocketClass::recvSocketData : %s " % exp)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            sendLogToStdout("%s %s %s" %(exc_type, exc_obj, exc_tb.tb_lineno))
            return None

    def close(self):

        sendLogToStdout("Closing client TCP Connection")
        msg = json.dumps("exit")
        self.sock.send(msg)

        self.sock.close()

class CRequestClass:

    def __init__(self, requestURL, httpMethod, httpPayload = ""):

        self._requestURL                = requestURL
        self._httpMethod                = httpMethod
        self._httpPayload               = httpPayload

    def GetJSONPayload(self):

        values = {"url" : self._requestURL, "method" : self._httpMethod, "data" : "" if (self._httpPayload is None) else (base64.b64encode(self._httpPayload)) }
        sendLogToStdout("Sending JSON values : %s" %values)
        return json.dumps(values)

###########################################Execution  Classes##########################################################################
class CHttpClass:
    '''
    This class process http request get/post/put
    '''
    def __init__(self, cfgReaderObj=None):
        '''
        Initializing class member variables in constructor
        '''
        self._httpSession                   = None
        self._userName                      = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "USERNAME")
        self._password                      = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "PASSWORD")
        self._contentType                   = CONTENT_TYPE
        self._encoded_login                 = base64.b64encode(b"%s:%s" %(self._userName, self._password))
        self._authorization                 = "Basic %s" %(self._encoded_login)
        if USE_ZEPHYR_PROXY == 1:
            self._tcpSession                    = CTCPSocketClass(ZEPHYR_PROXY_IP_ADDRESS, ZEPHYR_PROXY_PORT_NUMBER)
        self._httpGetRequestCountStats      = 0
        self._httpPutRequestCountStats      = 0
        self._httpPostRequestCountStats     = 0

    def getHttpSession(self):
        '''
        Returns current http session[SINGLETON object]
        :return:
        '''
        if self._httpSession is None:
            self._httpSession = requests.session()
            self._httpSession.headers.update({"Authorization":"%s" %self._authorization, "Content-Type":"%s" %self._contentType })
        return self._httpSession

    def get(self, requestURL):
        '''
        Process get http method
        :param requestURL:
        :return:
        '''
        sendLogToStdout("CHttpClass : get : %s" %requestURL)
        response = None
        self._httpGetRequestCountStats = self._httpGetRequestCountStats + 1
        if USE_ZEPHYR_PROXY == 0:
            response = self.getHttpSession().get(requestURL)
        else:
            #Code which will use zephyr proxy module to get a response
            request = CRequestClass(requestURL, "GET")
            response = self._tcpSession.processTCPRequest(request)
        sendLogToStdout("CHttpClass : Get Request count : %s" %self._httpGetRequestCountStats)
        sendLogToStdout("CHttpClass : get Response : %s" % response.json())
        return response

    def put(self, putURL, values=None):
        '''
        Process put http method
        :param putURL:
        :param values:
        :return:
        '''
        sendLogToStdout("CHttpClass : put : %s & values : %s" %(putURL,values))
        response = None
        self._httpPutRequestCountStats = self._httpPutRequestCountStats + 1
        if USE_ZEPHYR_PROXY == 0:
            response = self.getHttpSession().put(putURL, data = values)
        else:
            #Code which will use zephyr proxy module to get a response
            request = CRequestClass(putURL, "PUT", values)
            response = self._tcpSession.processTCPRequest(request)
        sendLogToStdout("CHttpClass : Put Request count : %s" %self._httpPutRequestCountStats)
        sendLogToStdout("CHttpClass : put Response : %s" % response.json())
        return response

    def post(self, postURL, values=None):
        '''
        Process post http method
        :param postURL:
        :param values:
        :return:
        '''
        sendLogToStdout("CHttpClass : post : %s & values : %s" %(postURL, values))
        response = None
        self._httpPostRequestCountStats = self._httpPostRequestCountStats + 1
        if USE_ZEPHYR_PROXY == 0:
            response = self.getHttpSession().post(postURL, data=values)
        else:
            #Code which will use zephyr proxy module to get a response
            request = CRequestClass(postURL, "POST", values)
            response = self._tcpSession.processTCPRequest(request)
        sendLogToStdout("CHttpClass : Post Request count : %s" %self._httpPostRequestCountStats)
        sendLogToStdout("CHttpClass : post Response : %s" % response.json())
        return response

    def close(self):

        if USE_ZEPHYR_PROXY != 0:
            self._tcpSession.close()


class CZephyr:
    '''
    This class implements functionality to manage different functionality of ZEPHYR
    '''
    _userName = None
    _password = None
    _contentType = None
    _autherization = None

    def __init__(self, cfgReaderObj, projectName, releaseName = None, templateCycleName = None,
                 templateCyclePhaseName = None ):
        '''
        Initializing class member variables in constructor
        :param projectName:
        :param releaseName:
        '''
        self._zephyrSession             = None
        self._tagList                   = ["toAuto", "automated", "updateAuto"]
        self._userName                  = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "USERNAME")
        self._password                  = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "PASSWORD")
        self._contentType               = CONTENT_TYPE
        self._encoded_login             = base64.b64encode(b"%s:%s" %(self._userName, self._password))
        self._authorization             = "Basic %s" %(self._encoded_login)
        self._projectName               = projectName
        self._releaseName               = releaseName
        self._templateCycleName         = templateCycleName
        self._templateCyclePhaseName    = templateCyclePhaseName
        self._projectDetails            = []     #Saves all the project information
        self._releaseDetails            = []     #Saved context of all release under single project
        self._projectDetail             = None   #Saves context of single project
        self._releaseCycleDetails       = []
        self._AutomationCycleDetail     = None
        self._newCycleDetail            = None
        self._completeProjectInfoList   = None
        self._userInfo                  = None
        self._cfgReaderObj              = cfgReaderObj
        self._ZephyrHostURL             = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "ZEPHYR_HOST")
        self._ZephyrRemotePath          = cfgReaderObj.get_config_param("ZEPHYR_CONFIG", "ZEPHYR_REMOTE_PATH")
        self._zephyrBaseURL             = self._ZephyrHostURL  + self._ZephyrRemotePath
        self._userId                    = self.getCurrentLoggedInUserDetails()
        self.UpdateProjectDetailContext()
        self.UpdateReleaseContext(self.getProjectID(self._projectName), self._releaseDetails)
        self._projectDetail = self.UpdateProjectDetailContextByProjectName(self._projectName)

    def updateProjectContext(self, ProjectName):

        projItem = None
        projItem = self.UpdateProjectDetailContextByProjectName(ProjectName)
        projId = self.getProjectID(ProjectName)

        releaseDetails = []
        self.UpdateReleaseContext(projId, releaseDetails)

        for releaseItem in releaseDetails:

            releaseCycles = []
            relId = releaseItem.id
            self.UpdateCycleDetailContextByReleaseID(relId, releaseCycles)

            releaseCycleVar = None
            if len(releaseCycles) <= 0:
                releaseCycleVar = None
            else:
                releaseCycleVar = releaseCycles

            if self._completeProjectInfoList is None:
                self._completeProjectInfoList = CZephyrProjectInfo(projItem, releaseItem, releaseCycleVar)
            else:
                self._completeProjectInfoList.appendProjectInfo(projItem, releaseItem, releaseCycleVar)

    def updateProjectCompleteContext(self):

        for projItem in self._projectDetails:

            projId = projItem.id
            projectList = ["NCI Longevity", "NCI Roku"]#, "NCI Android", "NCI iOS", "NCI tvOS", "NCI Adaptive Player"]

            for projectItemFromList in projectList:
                if (str(projItem.name) == projectItemFromList):

                    releaseDetails = []
                    self.UpdateReleaseContext(projId, releaseDetails)

                    for releaseItem in releaseDetails:

                        releaseCycles = []
                        relId = releaseItem.id
                        self.UpdateCycleDetailContextByReleaseID(relId, releaseCycles)

                        releaseCycleVar = None
                        if len(releaseCycles) <= 0:
                            releaseCycleVar = None
                        else:
                            releaseCycleVar = releaseCycles

                        if self._completeProjectInfoList is None:
                            self._completeProjectInfoList = CZephyrProjectInfo(projItem, releaseItem, releaseCycleVar)
                        else:
                            self._completeProjectInfoList.appendProjectInfo(projItem, releaseItem, releaseCycleVar)

    def GetJSONTagValue(self, jsonData, tag):

        if jsonData.has_key(tag) is True:
            return jsonData[tag]
        else:
            return None

    def getCurrentLoggedInUserDetails(self):
        '''
        Fetch user information for current logged in user
        :return:
        '''
        requestURL  = self._zephyrBaseURL + GET_USER_DETAILS
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("getCurrentLoggedInUserDetails: response.status_code : %s" %response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: getCurrentLoggedInUserDetails: HTTP error %s is received in response for GET request : %s" %(response.status_code, requestURL))
            return None

        jsonContent = response.json()

        userRolesList   = []
        userGroupsList  = []

        rolesJson = jsonContent["roles"]
        for role in rolesJson:
            rolesObj = CUserRoles(self.GetJSONTagValue(role, 'id'), self.GetJSONTagValue(role, 'name'),
                                  self.GetJSONTagValue(role, 'description'), self.GetJSONTagValue(role, 'hasManagerApp'))

            userRolesList.append(rolesObj)

        if "groups" in jsonContent.keys():
            groupsJson = jsonContent["groups"]
            for group in groupsJson:
                groupObj = CUserGroups( self.GetJSONTagValue(group, 'id'), self.GetJSONTagValue(group, 'name'),
                                        self.GetJSONTagValue(group, 'editable'), self.GetJSONTagValue(group, 'disabled'),
                                        self.GetJSONTagValue(group, 'canCreate'), self.GetJSONTagValue(group, 'canAssign'),
                                        self.GetJSONTagValue(group, 'canChangeState'), self.GetJSONTagValue(group, 'createdOn'))

                userGroupsList.append(groupObj)

        self._userInfo = CUserInfo(self.GetJSONTagValue(jsonContent, 'id'), self.GetJSONTagValue(jsonContent, 'username'),
                                   self.GetJSONTagValue(jsonContent, 'firstName'), self.GetJSONTagValue(jsonContent, 'lastName'),
                                   self.GetJSONTagValue(jsonContent, 'location'), self.GetJSONTagValue(jsonContent, 'type'),
                                   self.GetJSONTagValue(jsonContent, 'email'), self.GetJSONTagValue(jsonContent, 'accountEnabled'),
                                   self.GetJSONTagValue(jsonContent, 'accountExpired'), self.GetJSONTagValue(jsonContent, 'credentialsExpired'),
                                   self.GetJSONTagValue(jsonContent, 'loginName'), userRolesList, self.GetJSONTagValue(jsonContent, 'userType'),
                                   self.GetJSONTagValue(jsonContent, 'chargeableFlag'), self.GetJSONTagValue(jsonContent, 'lastSuccessfulLogin'),
                                   self.GetJSONTagValue(jsonContent, 'lastSuccessfulLoginString'), userGroupsList,
                                   self.GetJSONTagValue(jsonContent, 'fullName'))
        return self._userInfo.id

    def getZephyrSession(self):
        '''
        Returns current active zephyr session[SINGLETON object]
        :return:
        '''
        if self._zephyrSession is None:
            self._zephyrSession = CHttpClass(self._cfgReaderObj)
        return self._zephyrSession

    def closeZephyrSession(self):

        if self._zephyrSession is not None:
            self._zephyrSession.close()

    def UpdateProjectDetailContext(self):
        '''
        This function fetch project id by projectName
        :return:
        '''
        requestURL  = self._zephyrBaseURL + LIST_ALL_PROJECTS
        response    = (self.getZephyrSession()).get(requestURL)


        sendLogToStdout("UpdateProjectDetailContext: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: UpdateProjectDetailContext: HTTP error %s is received in response for GET request : %s" %(response.status_code, requestURL))
            return False

        jsonContent = response.json()
        for item in jsonContent:
            projectDetail = CProjectDetail(self.GetJSONTagValue(item, 'id'),self.GetJSONTagValue(item, 'version'),
                                           self.GetJSONTagValue(item, 'name'), self.GetJSONTagValue(item, 'description'),
                                           self.GetJSONTagValue(item, 'startDate'), self.GetJSONTagValue(item, 'projectStartDate'),
                                           self.GetJSONTagValue(item, 'status'), self.GetJSONTagValue(item, 'showItem'),
                                           self.GetJSONTagValue(item, 'newItem'), self.GetJSONTagValue(item, 'members'),
                                           self.GetJSONTagValue(item, 'isolationLevel'), self.GetJSONTagValue(item, 'dashboardSecured'),
                                           self.GetJSONTagValue(item, 'dashboardUrl'), self.GetJSONTagValue(item, 'dashboardRestricted'),
                                           self.GetJSONTagValue(item, 'createdOn'), self.GetJSONTagValue(item, 'shared'))

            self._projectDetails.append(projectDetail)
        return True

    def UpdateProjectDetailContextByProjectName(self, projName):
        '''
        This function fetch project id by projectName
        :return:
        '''
        projTemp = None
        for projItem in self._projectDetails:
            if projName == projItem.name:
                projTemp = projItem
                break

        if projTemp is None:
            return False
        return projTemp

    def getTestCaseCountByCycleTcrCatalogTreeId(self, CycleTcrCatalogTreeId, releaseId):
        '''
        Get test case count by Cycle Phase ID
        :param CycleTcrCatalogTreeId:
        :return:
        '''

        rep = {"TCR_CATALOG_TREE_ID": str(CycleTcrCatalogTreeId), "RELEASE_ID": str(releaseId)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], GET_COUNT_TESTCASES_BY_PHASE)

        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getTestCaseCountByCycleTcrCatalogTreeId: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: getTestCaseCountByCycleTcrCatalogTreeId: HTTP error %s is received in response for GET request : %s" %(response.status_code, requestURL))
            return None

        testCaseCount = response.json()
        return int (testCaseCount)

    def getProjectID(self, projectName):
        '''
        Get project ID by project name
        :param projectName:
        :return:
        '''
        projectId = None
        for projectDetail in self._projectDetails:
            if projectDetail.name == projectName:
                projectId = projectDetail.id
                break
        return projectId


    def UpdateReleaseContext(self, projId, releaseContext):
        '''
        Fetch all release created under project name
        :param projectName:
        :return:
        '''

        requestURL = self._zephyrBaseURL + LIST_ALL_RELEASES.replace("PROJECTID", str(projId))
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("UpdateReleaseContext: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: UpdateReleaseContext: HTTP error %s is received in response for GET request : %s" %(response.status_code, requestURL))
            return False

        jsonContent = response.json()
        for item in jsonContent:
            externalSystem = None

            relDetail = CReleaseDetail( self.GetJSONTagValue(item, 'id'), self.GetJSONTagValue(item, 'name'),
                                        self.GetJSONTagValue(item, 'description'), self.GetJSONTagValue(item, 'startDate'),
                                        self.GetJSONTagValue(item, 'releaseStartDate'), self.GetJSONTagValue(item, 'endDate'),
                                        self.GetJSONTagValue(item, 'releaseEndDate'), self.GetJSONTagValue(item, 'createdDate'),
                                        self.GetJSONTagValue(item, 'status'), self.GetJSONTagValue(item, 'external_system'),
                                        self.GetJSONTagValue(item, 'projectId'), self.GetJSONTagValue(item, 'orderId'))

            releaseContext.append(relDetail)
        return True


    def getReleaseId(self, releaseName):
        '''
        Fetch releaseId by release name
        :param ReleaseName:
        :return:
        '''
        releaseId = None
        for releaseDetail in self._releaseDetails:
            lReleaseName = releaseDetail.name.replace(' ', '')
            if lReleaseName == releaseName.replace(' ', ''):
                releaseId = releaseDetail.id
        return releaseId

    def UpdateAutomationCycleDetailContext(self):
        '''
        Fetch cycle Detail for cycle name under release name
        :param cycleName:
        :param releaseName:
        :return:
        '''
        release_id = self.getReleaseId(self._releaseName)
        requestURL = self._zephyrBaseURL + GET_CYCLE_PHASE.replace("RELEASEID", str(release_id))
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("UpdateAutomationCycleDetailContext: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: UpdateAutomationCycleDetailContext: HTTP error %s is received in response for GET request : %s" % (response.status_code, requestURL))
            return False

        jsonContent = response.json()

        for item in jsonContent:
            AutomationCyclePhaseList = []
            if item["name"] == self._templateCycleName:
                CyclePhaseContent   =   item["cyclePhases"]
                for cyclePhase in CyclePhaseContent:
                    AutomationCylePhaseObj   = AutomationCyclePhase( self.GetJSONTagValue(cyclePhase, 'id'), self.GetJSONTagValue(cyclePhase, 'name'),
                                                                     self.GetJSONTagValue(cyclePhase, 'tcrCatalogTreeId'), self.GetJSONTagValue(cyclePhase, 'freeForm'),
                                                                     self.GetJSONTagValue(cyclePhase, 'startDate'), self.GetJSONTagValue(cyclePhase, 'endDate'),
                                                                     self.GetJSONTagValue(cyclePhase, 'createdOn'), self.GetJSONTagValue(cyclePhase, 'cycleId'),
                                                                     self.GetJSONTagValue(cyclePhase, 'phaseStartDate'), self.GetJSONTagValue(cyclePhase, 'phaseEndDate'))

                    AutomationCyclePhaseList.append(AutomationCylePhaseObj)

                self._AutomationCycleDetail =  AutomationCycleDetail( self.GetJSONTagValue(item, 'id'), self.GetJSONTagValue(item, 'environment'),
                                                                      self.GetJSONTagValue(item, 'build'), self.GetJSONTagValue(item, 'name'),
                                                                      self.GetJSONTagValue(item, 'startDate'), self.GetJSONTagValue(item, 'endDate'),
                                                                      self.GetJSONTagValue(item, 'cycleStartDate'), self.GetJSONTagValue(item, 'cycleEndDate'),
                                                                      self.GetJSONTagValue(item, 'status'), self.GetJSONTagValue(item, 'revision'),
                                                                      self.GetJSONTagValue(item, 'releaseId'), AutomationCyclePhaseList,
                                                                      self.GetJSONTagValue(item, 'createdOn'))
                break
        return True


    def UpdateCycleDetailContextByReleaseID(self, releaseId, cycleContext):
        '''
        Fetch cycle Detail for cycle name under release name
        :param cycleName:
        :param releaseName:
        :return:
        '''

        requestURL = self._zephyrBaseURL + GET_CYCLE_PHASE.replace("RELEASEID", str(releaseId))
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("UpdateAutomationCycleDetailContext: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: UpdateAutomationCycleDetailContext: HTTP error %s is received in response for GET request : %s" % (response.status_code, requestURL))
            return False

        jsonContent = response.json()

        for item in jsonContent:
            AutomationCyclePhaseList = []
            CyclePhaseContent   =   item["cyclePhases"]
            for cyclePhase in CyclePhaseContent:
                AutomationCylePhaseObj   = AutomationCyclePhase( self.GetJSONTagValue(cyclePhase, 'id'), self.GetJSONTagValue(cyclePhase, 'name'),
                                                                 self.GetJSONTagValue(cyclePhase, 'tcrCatalogTreeId'), self.GetJSONTagValue(cyclePhase, 'freeForm'),
                                                                 self.GetJSONTagValue(cyclePhase, 'startDate'), self.GetJSONTagValue(cyclePhase, 'endDate'),
                                                                 self.GetJSONTagValue(cyclePhase, 'createdOn'), self.GetJSONTagValue(cyclePhase, 'cycleId'),
                                                                 self.GetJSONTagValue(cyclePhase, 'phaseStartDate'), self.GetJSONTagValue(cyclePhase, 'phaseEndDate'))

                AutomationCyclePhaseList.append(AutomationCylePhaseObj)

            cycleContext.append(AutomationCycleDetail( self.GetJSONTagValue(item, 'id'), self.GetJSONTagValue(item, 'environment'),
                                                                  self.GetJSONTagValue(item, 'build'), self.GetJSONTagValue(item, 'name'),
                                                                  self.GetJSONTagValue(item, 'startDate'), self.GetJSONTagValue(item, 'endDate'),
                                                                  self.GetJSONTagValue(item, 'cycleStartDate'), self.GetJSONTagValue(item, 'cycleEndDate'),
                                                                  self.GetJSONTagValue(item, 'status'), self.GetJSONTagValue(item, 'revision'),
                                                                  self.GetJSONTagValue(item, 'releaseId'), AutomationCyclePhaseList,
                                                                  self.GetJSONTagValue(item, 'createdOn')))
        return True

    def getCycleInfo(self, phaseName, cycleName):
        '''
        Fetch phase planned in current cycle under release name
        :param phaseName:
        :return:
        '''
        cycleId, cyclePhaseId = None, None
        if self._AutomationCycleDetail.name == cycleName:
            for item in self._AutomationCycleDetail.cyclePhases:
                if (item.name == phaseName):
                    cycleId = self._AutomationCycleDetail.id
                    cyclePhaseId = item.id
                    break;

        return cycleId, cyclePhaseId

    def getCyclePhasList(self, releaseId, cycleId, PhaseNameSubStr):

        cyclePhaseDict = {}
        releaseCycles = []

        self.UpdateCycleDetailContextByReleaseID(releaseId, releaseCycles)

        for cycleItem in releaseCycles:
            if cycleItem.id == cycleId:
                for cyclePhaseItem in cycleItem.cyclePhases:
                    if PhaseNameSubStr in str(cyclePhaseItem.name):
                        cyclePhaseDict[str(cyclePhaseItem.name)] = cyclePhaseItem
        return cyclePhaseDict

    def getCyclePhaseByName(self, releaseId, cycleId, cyclePhaseName):

        cyclePhaseInfo = None
        releaseCycles  = []

        self.UpdateCycleDetailContextByReleaseID(releaseId, releaseCycles)

        for cycleItem in releaseCycles:
            if cycleItem.id == cycleId:
                for cyclePhaseItem in cycleItem.cyclePhases:
                    if cyclePhaseItem.name == cyclePhaseName:
                        cyclePhaseInfo = copy.copy(cyclePhaseItem)
                        break
        return cyclePhaseInfo

    def getCycleInfoByName(self, releaseId, cycleName):

        cycleInfo = None
        releaseCycles = []

        self.UpdateCycleDetailContextByReleaseID(releaseId, releaseCycles)

        for cycleItem in releaseCycles:
            if cycleItem.name == cycleName:
                cycleInfo = copy.copy(cycleItem)
                break
        return cycleInfo

    def cloneCycle(self, newCycleName, deep, copyAssignment):
        '''
        Clone automation cycle template under project name and copy all phase and executions
        :param projectName:
        :param newCycleName:
        :param deep:
        :param copyAssignment:
        :return:
        '''
        currentDate = datetime.datetime.today().strftime("%d/%b/%y")

        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        EndDateEpochTimeinMS = StartDateEpochTimeinMS + 86400000

        templateCyclePhase  = None
        for cyclePhase in self._AutomationCycleDetail.cyclePhases:
            if cyclePhase.name == self._templateCyclePhaseName:
                templateCyclePhase = cyclePhase

        newCycle = CreateNewCycle(self._AutomationCycleDetail.id, self._AutomationCycleDetail.environment, self._AutomationCycleDetail.build,
                                  newCycleName, StartDateEpochTimeinMS, EndDateEpochTimeinMS, currentDate, currentDate,
                                  self._AutomationCycleDetail.status, self._AutomationCycleDetail.revision, self._AutomationCycleDetail.releaseId,
                                  templateCyclePhase.GetJSONPayload(), self._AutomationCycleDetail.createdOn, self._releaseName,
                                  self._projectName, self.getProjectID(self._projectName))

        values = newCycle.GetJSONPayload()
        rep = {"CYCLEID": str(self._AutomationCycleDetail.id), "DEEPFLAG": str(deep), "COPYASSIGN": str(copyAssignment)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], CLONE_CYCLE)

        postURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).post(postURL, values)

        sendLogToStdout("cloneCycle: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: cloneCycle: HTTP error %s is received in response for POST request : %s" % (response.status_code, postURL))
            return None, None

        jsonContent = response.json()

        newCyclePhaseJson = jsonContent["cyclePhases"]

        newAutomationCyclePhaseList = []
        for cyclePhase in newCyclePhaseJson:
            newAutomationCylePhaseObj = AutomationCyclePhase(self.GetJSONTagValue(cyclePhase, 'id'), self.GetJSONTagValue(cyclePhase, 'name'),
                                                          self.GetJSONTagValue(cyclePhase, 'tcrCatalogTreeId'), self.GetJSONTagValue(cyclePhase, 'freeForm'),
                                                          self.GetJSONTagValue(cyclePhase, 'startDate'), self.GetJSONTagValue(cyclePhase, 'endDate'),
                                                          self.GetJSONTagValue(cyclePhase, 'createdOn'), self.GetJSONTagValue(cyclePhase, 'cycleId'),
                                                          self.GetJSONTagValue(cyclePhase, 'phaseStartDate'), self.GetJSONTagValue(cyclePhase, 'phaseEndDate'))

            newAutomationCyclePhaseList.append(newAutomationCylePhaseObj)

        self._newCycleDetail = AutomationCycleDetail( self.GetJSONTagValue(jsonContent, 'id'), self.GetJSONTagValue(jsonContent, 'environment'),
                                                      self.GetJSONTagValue(jsonContent, 'build'), self.GetJSONTagValue(jsonContent, 'name'),
                                                      self.GetJSONTagValue(jsonContent, 'startDate'), self.GetJSONTagValue(jsonContent, 'endDate'),
                                                      self.GetJSONTagValue(jsonContent, 'cycleStartDate'), self.GetJSONTagValue(jsonContent, 'cycleEndDate'),
                                                      self.GetJSONTagValue(jsonContent, 'status'), self.GetJSONTagValue(jsonContent, 'revision'),
                                                      self.GetJSONTagValue(jsonContent, 'releaseId'), newAutomationCyclePhaseList,
                                                      self.GetJSONTagValue(jsonContent, 'createdOn'))

        newCyclePhaseObj = None
        for item in self._newCycleDetail.cyclePhases:
            if (item.name == templateCyclePhase.name):
                newCyclePhaseObj = item

        self.UpdateAutomationCycleDetailContext()
        return newCyclePhaseObj.id, newCyclePhaseObj.tcrCatalogTreeId

    def getTestCasesForAssignmentByCyclePhaseId(self, cyclePhaseId, testCaseId):
        '''
        Get All test cases scheduled in cycle Phase ID
        :param cyclePhaseId:
        :return:
        '''
        requestURL = self._zephyrBaseURL + GET_TEST_CASES_FOR_ASSIGN.replace("CYCLE_PHASE_ID", str(cyclePhaseId))
        response   = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getTestCasesForAssignmentByCyclePhaseId: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: getTestCasesForAssignmentByCyclePhaseId: HTTP error %s is received in response for POST request : %s" % (response.status_code, requestURL))
            return None

        jsonContent = response.json()

        testCaseJson = jsonContent["testcase"]
        testCaseObj = CTestCase(self.GetJSONTagValue(testCaseJson, 'customProperties'), self.GetJSONTagValue(testCaseJson, 'customProcessedProperties'),
                                self.GetJSONTagValue(testCaseJson, 'id'), self.GetJSONTagValue(testCaseJson, 'name'),
                                self.GetJSONTagValue(testCaseJson, 'externalId'), self.GetJSONTagValue(testCaseJson, 'priority'),
                                self.GetJSONTagValue(testCaseJson, 'tag'), self.GetJSONTagValue(testCaseJson, 'description'),
                                self.GetJSONTagValue(testCaseJson, 'lastModifiedOn'), self.GetJSONTagValue(testCaseJson, 'creationDate'),
                                self.GetJSONTagValue(testCaseJson, 'tcCreationDate'), self.GetJSONTagValue(testCaseJson, 'comments'),
                                self.GetJSONTagValue(testCaseJson, 'isComplex'), self.GetJSONTagValue(testCaseJson, 'estimatedTime'),
                                self.GetJSONTagValue(testCaseJson, 'writerId'), self.GetJSONTagValue(testCaseJson, 'creatorId'),
                                self.GetJSONTagValue(testCaseJson, 'lastUpdaterId'), self.GetJSONTagValue(testCaseJson, 'oldId'),
                                self.GetJSONTagValue(testCaseJson, 'automated'), self.GetJSONTagValue(testCaseJson, 'scriptName'),
                                self.GetJSONTagValue(testCaseJson, 'requirementIds'), self.GetJSONTagValue(testCaseJson, 'releaseId'),
                                self.GetJSONTagValue(testCaseJson, 'customFieldProcessed'), self.GetJSONTagValue(testCaseJson, 'customFieldValues'),
                                self.GetJSONTagValue(testCaseJson, 'versionNumber'), self.GetJSONTagValue(testCaseJson, 'shared'),
                                self.GetJSONTagValue(testCaseJson, 'projectId'), self.GetJSONTagValue(testCaseJson, 'sourceTestcaseId'),
                                self.GetJSONTagValue(testCaseJson, 'sourceTestcaseVersionNumber'), self.GetJSONTagValue(testCaseJson, 'automatedDefault'))

        testCaseVersionJson = jsonContent["testcaseVersion"]
        testCaseVersionObj = CTestCaseVersion(self.GetJSONTagValue(testCaseVersionJson, 'customProperties'), self.GetJSONTagValue(testCaseVersionJson, 'customProcessedProperties'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'id'), self.GetJSONTagValue(testCaseVersionJson, 'name'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'description'), self.GetJSONTagValue(testCaseVersionJson, 'tag'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'lastModifiedOn'), self.GetJSONTagValue(testCaseVersionJson, 'creationDate'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'tcCreationDate'), self.GetJSONTagValue(testCaseVersionJson, 'comments'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'isComplex'), self.GetJSONTagValue(testCaseVersionJson, 'estimatedTime'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'creatorId'), self.GetJSONTagValue(testCaseVersionJson, 'lastUpdaterId'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'oldId'), self.GetJSONTagValue(testCaseVersionJson, 'automated'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'scriptName'), self.GetJSONTagValue(testCaseVersionJson, 'releaseId'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'customFieldProcessed'), self.GetJSONTagValue(testCaseVersionJson, 'customFieldValues'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'testcaseId'), self.GetJSONTagValue(testCaseVersionJson, 'versionNumber'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'projectId'), self.GetJSONTagValue(testCaseVersionJson, 'versionCreatedBy'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'versionCreationDate'), self.GetJSONTagValue(testCaseVersionJson, 'sourceTestcaseId'),
                                              self.GetJSONTagValue(testCaseVersionJson, 'sourceTestcaseVersionNumber'), self.GetJSONTagValue(testCaseVersionJson, 'automatedDefault'))

        tcrTreeTestCaseJson = jsonContent
        tcrTreeTestCaseObj = CTcrTreeTestCase(self.GetJSONTagValue(tcrTreeTestCaseJson, 'id'), self.GetJSONTagValue(tcrTreeTestCaseJson, 'tcrCatalogTreeId'),
                                              testCaseObj, self.GetJSONTagValue(tcrTreeTestCaseJson, 'revision'),
                                              self.GetJSONTagValue(tcrTreeTestCaseJson, 'stateFlag'), self.GetJSONTagValue(tcrTreeTestCaseJson, 'lastModifiedOn'),
                                              self.GetJSONTagValue(tcrTreeTestCaseJson, 'versionNumber'), testCaseVersionObj,
                                              self.GetJSONTagValue(tcrTreeTestCaseJson, 'original'))

        return tcrTreeTestCaseObj

    def assignCyclePhaseTestCases(self, cyclePhaseId, tcrCatalogTreeId):
        '''
        Update cycle phase values
        :param newCyclePhaseName:
        :param cycleId:
        :param cyclePhaseID:
        :return:
        '''
        rep = {"CYCLE_PHASE_ID": str(cyclePhaseId), "TCR_CATALOG_TREE_ID": str(tcrCatalogTreeId),
               "TESTER_ID": str(self._userId)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], CHANGE_ASSIGNMENTS)

        putURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession().put(putURL, None))

        sendLogToStdout("assignCyclePhaseTestCases: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: assignCyclePhaseTestCases: HTTP error %s is received in response for PUT request : %s" % (response.status_code, putURL))
            return False

        self.UpdateAutomationCycleDetailContext()
        return True

    def clonePhase(self, cycleId, cyclePhaseId):
        '''
        Clones cycle phase
        :param phaseNameTemplate:
        :return:
        '''
        postURL = self._zephyrBaseURL + CLONE_CYCLE_PHASE.replace("CYCLE_PHASE_ID", str(cyclePhaseId))
        response = (self.getZephyrSession()).post(postURL, None)

        sendLogToStdout("clonePhase: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: clonePhase: HTTP error %s is received in response for POST request : %s" % (response.status_code, postURL))
            return None, None

        responseJson = response.json()

        AutomationCylePhaseObj = AutomationCyclePhase(self.GetJSONTagValue(responseJson, 'id'), self.GetJSONTagValue(responseJson, 'name'),
                                                      self.GetJSONTagValue(responseJson, 'tcrCatalogTreeId'), self.GetJSONTagValue(responseJson, 'freeForm'),
                                                      self.GetJSONTagValue(responseJson, 'startDate'), self.GetJSONTagValue(responseJson, 'endDate'),
                                                      self.GetJSONTagValue(responseJson, 'createdOn'), cycleId,
                                                      self.GetJSONTagValue(responseJson, 'phaseStartDate'), self.GetJSONTagValue(responseJson, 'phaseEndDate'))

        self._AutomationCycleDetail.cyclePhases.append(AutomationCylePhaseObj)

        self.UpdateAutomationCycleDetailContext()

        return AutomationCylePhaseObj.id, AutomationCylePhaseObj.tcrCatalogTreeId


    def createZephyrCycle(self, cycleName, releaseId, environemnt, build, cyclePhaseList, isCycleHidden = True):

        valueDict = {}
        zephyrCycleInfo = None

        currentDate = datetime.datetime.today().strftime("%m/%d/%Y")

        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        EndDateEpochTimeinMS = StartDateEpochTimeinMS + 86400000

        valueDict["name"]              = cycleName
        valueDict["environment"]       = environemnt
        valueDict["build"]             = build
        valueDict["startDate"]         = StartDateEpochTimeinMS
        valueDict["endDate"]           = EndDateEpochTimeinMS
        valueDict["cycleStartDate"]    = currentDate
        valueDict["cycleEndDate"]      = currentDate
        valueDict["status"]            = (1 if isCycleHidden is True else 0)
        valueDict["releaseId"]         = releaseId
        valueDict["cyclePhases"]       = cyclePhaseList
        valueDict["createdOn"]         = StartDateEpochTimeinMS

        values = json.dumps(valueDict)

        postURL = self._zephyrBaseURL + CREATE_CYCLE
        response = (self.getZephyrSession()).post(postURL, values)

        sendLogToStdout("createZephyrCycle: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: createZephyrCycle: HTTP error %s is received in response for POST request : %s" % (
            response.status_code, postURL))
            return None, None

        responseJson = response.json()

        zephyrCycleInfo = AutomationCycleDetail(self.GetJSONTagValue(responseJson, 'id'),
                                                self.GetJSONTagValue(responseJson, 'environment'),
                                                self.GetJSONTagValue(responseJson, 'build'),
                                                self.GetJSONTagValue(responseJson, 'name'),
                                                self.GetJSONTagValue(responseJson, 'startDate'),
                                                self.GetJSONTagValue(responseJson, 'endDate'),
                                                self.GetJSONTagValue(responseJson, 'cycleStartDate'),
                                                self.GetJSONTagValue(responseJson, 'cycleEndDate'),
                                                self.GetJSONTagValue(responseJson, 'status'),
                                                self.GetJSONTagValue(responseJson, 'revision'),
                                                self.GetJSONTagValue(responseJson, 'releaseId'),
                                                self.GetJSONTagValue(responseJson, 'cyclePhases'),
                                                self.GetJSONTagValue(responseJson, 'createdOn'))

        return zephyrCycleInfo


    def createPhase(self, cycleInfo, cyclePhaseName, freeform=True):

        valueDict = {}
        zephyrPhaseInfo = None

        currentDate = datetime.datetime.today().strftime("%d/%b/%Y")

        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        EndDateEpochTimeinMS = StartDateEpochTimeinMS + 86400000

        valueDict["name"] = cyclePhaseName
        valueDict["phaseStartDate"] = cycleInfo.cycleStartDate
        valueDict["phaseEndDate"] = cycleInfo.cycleEndDate
        valueDict["cycleId"] = cycleInfo.id
        valueDict["releaseId"] = cycleInfo.releaseId
        valueDict["freeForm"] = freeform

        values = json.dumps(valueDict)

        postURL = self._zephyrBaseURL + CREATE_PHASE.replace("CYCLE_ID", str(cycleInfo.id))
        response = (self.getZephyrSession()).post(postURL, values)

        sendLogToStdout("createPhase: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: createPhase: HTTP error %s is received in response for POST request : %s" % (
                response.status_code, postURL))
            return None, None

        responseJson = response.json()

        zephyrPhaseInfo = AutomationCyclePhase(self.GetJSONTagValue(responseJson, 'id'),
                                                      self.GetJSONTagValue(responseJson, 'name'),
                                                      self.GetJSONTagValue(responseJson, 'tcrCatalogTreeId'),
                                                      self.GetJSONTagValue(responseJson, 'freeForm'),
                                                      self.GetJSONTagValue(responseJson, 'startDate'),
                                                      self.GetJSONTagValue(responseJson, 'endDate'),
                                                      self.GetJSONTagValue(responseJson, 'createdOn'),
                                                      self.GetJSONTagValue(responseJson, 'cycleId'),
                                                      self.GetJSONTagValue(responseJson, 'phaseStartDate'),
                                                      self.GetJSONTagValue(responseJson, 'phaseEndDate'))

        return zephyrPhaseInfo


    def getCyclePhaseTreeIdForAssignement(self, cyclePhaseId):

        assignedUserList    =   []
        categoriesList      =   []

        requestURL = self._zephyrBaseURL + GET_ASSIGNMENT_TREEID.replace("CYCLE_PHASE_ID", str(cyclePhaseId))
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getCyclePhaseTreeIdForAssignement: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                "ERROR: getCyclePhaseTreeIdForAssignement: HTTP error %s is received in response for POST request : %s" % (
                response.status_code, requestURL))
            return None

        jsonContent = response.json()

        assignedUserList            = jsonContent["assignedUsers"]
        categoriesList              = jsonContent["categories"]

        phaseTreeAssignmentInfoObj  =   CPhaseTreeAssignmentInfo(self.GetJSONTagValue(jsonContent, 'id'),
                                                      self.GetJSONTagValue(jsonContent, 'type'),
                                                      self.GetJSONTagValue(jsonContent, 'name'),
                                                      self.GetJSONTagValue(jsonContent, 'description'),
                                                      self.GetJSONTagValue(jsonContent, 'revision'),
                                                      categoriesList,
                                                      assignedUserList,
                                                      self.GetJSONTagValue(jsonContent, 'releaseId'),
                                                      self.GetJSONTagValue(jsonContent, 'linkedTCRCatalogTreeId'),
                                                      self.GetJSONTagValue(jsonContent, 'createdOn'),
                                                      self.GetJSONTagValue(jsonContent, 'lastModifiedOn'))

        return phaseTreeAssignmentInfoObj

    def performAllCyclePhaseTreeIdAssignement(self, cyclePhaseId):

        testCaseIdToInfoDict        = {}

        requestURL = self._zephyrBaseURL + GET_ASSIGNMENT_TREEID.replace("CYCLE_PHASE_ID", str(cyclePhaseId))
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getCyclePhaseTreeIdForAssignement: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                "ERROR: getCyclePhaseTreeIdForAssignement: HTTP error %s is received in response for POST request : %s" % (
                response.status_code, requestURL))
            return None

        jsonContent = response.json()

        assignedUserList = jsonContent["assignedUsers"]


        phaseTreeAssignmentInfoObj = CPhaseTreeAssignmentInfo(self.GetJSONTagValue(jsonContent, 'id'),
                                                              self.GetJSONTagValue(jsonContent, 'type'),
                                                              self.GetJSONTagValue(jsonContent, 'name'),
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'description'),
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'revision'),
                                                              self.parseTreeAsignementReponse(cyclePhaseId, jsonContent, testCaseIdToInfoDict),
                                                              assignedUserList,
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'releaseId'),
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'linkedTCRCatalogTreeId'),
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'createdOn'),
                                                              self.GetJSONTagValue(jsonContent,
                                                                                   'lastModifiedOn'))
        self.assignCyclePhaseTestCases(cyclePhaseId, phaseTreeAssignmentInfoObj.id)

        testCaseIdToInfoDict[phaseTreeAssignmentInfoObj.id]     =   phaseTreeAssignmentInfoObj

        return testCaseIdToInfoDict

    def parseTreeAsignementReponse(self, cyclePhaseId, jsonContent, testCaseIdToInfoDict):

        categoriesListObj = []
        categoryListObj    = jsonContent["categories"]
        if len(categoryListObj) <= 0:
            return None
        else:
            for categoryItem in categoryListObj:
                self.parseTreeAsignementReponse(cyclePhaseId, categoryItem, testCaseIdToInfoDict)
                assignedUserList = categoryItem["assignedUsers"]
                categoriesList = categoryItem["categories"]

                phaseTreeAssignmentInfoObj = CPhaseTreeAssignmentInfo(self.GetJSONTagValue(categoryItem, 'id'),
                                                                      self.GetJSONTagValue(categoryItem, 'type'),
                                                                      self.GetJSONTagValue(categoryItem, 'name'),
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'description'),
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'revision'),
                                                                      categoriesList,
                                                                      assignedUserList,
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'releaseId'),
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'linkedTCRCatalogTreeId'),
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'createdOn'),
                                                                      self.GetJSONTagValue(categoryItem,
                                                                                           'lastModifiedOn'))
                self.assignCyclePhaseTestCases(cyclePhaseId, phaseTreeAssignmentInfoObj.id)
                testCaseIdToInfoDict[phaseTreeAssignmentInfoObj.id] = phaseTreeAssignmentInfoObj
                categoriesListObj.append(phaseTreeAssignmentInfoObj)
        return categoriesListObj

    def getTestCaseListByZephyrTestFolder(self, releaseId, folderPath, testCaseTreeIdList, tagName):

        folderHierarchiy = folderPath
        finalPathURL = FETCH_ALL_TEST_CASE.replace("RELEASE_ID", str(releaseId))
        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession().get(requestURL)).json()

        SplitFolderStructure = folderHierarchiy.split(":")

        result = self.getTestCaseTreeIdbyFolderHeirarchy(response, SplitFolderStructure)

        if (result is None ) :
            sendLogToStdout("getTestCaseListByZephyrTestFolder: Incorrect Zephyr test repository path : %s" %folderPath)
            return False

        jsonResp = []
        jsonResp.append(result)
        self.getTestRepoTreeId(jsonResp, testCaseTreeIdList, tagName)

        return True

    def getTestRepoTreeId(self, testRepoDiretoryJSON, testCaseTreeIdList, tagName):

        for testRepoFolder in testRepoDiretoryJSON:

            categoryList = testRepoFolder["categories"]
            testCaseTreeIdDict = {}
            testCaseList = CTestRepositoryTestCaseInfo()
            jsonContent = self.getTestCaseListByTreeId(testRepoFolder["id"])

            if (jsonContent['resultSize'] > 0) :
                for testCase in jsonContent['results']:
                    testCaseList.append(self.getTestCasesObject(testCase))

            testCasebyTagList, count = self.getTestCaseCountByTag(testCaseList, tagName)

            testCaseTreeIdDict["treeid"] = testRepoFolder["id"]
            testCaseTreeIdDict["isExclusion"] = True

            if count > 0:
                testCaseZephyrID = []
                for testCaseObj in testCasebyTagList:
                    testCaseZephyrID.append(testCaseObj.testcaseObj.id)
                testCaseTreeIdDict["tctIds"] = testCaseZephyrID
            else:
                testCaseTreeIdDict["tctIds"] = []
            testCaseTreeIdList.append(testCaseTreeIdDict)
            if len(categoryList) > 0:
                self.getTestRepoTreeId(categoryList, testCaseTreeIdList, tagName)

    def getTestCaseTreeIdbyFolderHeirarchy(self, responseJson, folderHierarchiy):

        for testRepoFolder in responseJson:
            folderName = testRepoFolder["name"]

            if folderHierarchiy[0] == folderName:
                folderHierarchiy.remove(folderName)
            else:
                continue
            categoryList = testRepoFolder["categories"]

            if len(categoryList) <= 0:
                if (len(folderHierarchiy) <= 0):
                    return testRepoFolder
                else:
                    return None
            else:
                if (len(folderHierarchiy) <= 0):
                    return testRepoFolder
                else:
                    retVal =  self.getTestCaseTreeIdbyFolderHeirarchy(categoryList, folderHierarchiy)
                    return retVal

    def getAutomatedTestCasesByZQLQuery(self, releaseId, projectID):

        testCaseList    = []
        rep = {"RELEASE_ID": str(releaseId), "PROJECT_ID": str(projectID)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], FETCH_AUTOMATED_TEST_CASE)

        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getAutomatedTestCasesByZQLQuery: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                "ERROR: getAutomatedTestCasesByZQLQuery: HTTP error %s is received in response for POST request : %s" % (
                    response.status_code, requestURL))
            return None

        responseJson = response.json()

        jsonContent = responseJson[0]["results"]

        for testResult in jsonContent:
            testCaseJson = testResult["testcase"]
            customFieldValueJson    = testCaseJson["customFieldValues"]
            customFieldValueListObj = []

            for customFieldValueItem in customFieldValueJson:

                customFieldValueObj = CTestCaseCustomFieldValue(self.GetJSONTagValue(customFieldValueItem, 'displayName'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'value'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'testcaseVersionId'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'pickListValue'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'fieldName'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'fieldTypeMetadata'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'fieldId'),
                                                                self.GetJSONTagValue(customFieldValueItem, 'id'))
                customFieldValueListObj.append(customFieldValueObj)

            testCaseObj = CTestCase(self.GetJSONTagValue(testCaseJson, 'lastModifiedOn'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIds'),
                                    self.GetJSONTagValue(testCaseJson, 'customFieldProcessed'),
                                    self.GetJSONTagValue(testCaseJson, 'tag'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIdsNew'),
                                    self.GetJSONTagValue(testCaseJson, 'tcCreationData'),
                                    self.GetJSONTagValue(testCaseJson, 'customProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'id'),
                                    self.GetJSONTagValue(testCaseJson, 'description'),
                                    self.GetJSONTagValue(testCaseJson, 'estimatedTime'),
                                    self.GetJSONTagValue(testCaseJson, 'projectId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseType'),
                                    self.GetJSONTagValue(testCaseJson, 'automationDefault'),
                                    self.GetJSONTagValue(testCaseJson, 'comments'),
                                    self.GetJSONTagValue(testCaseJson, 'priority'),
                                    self.GetJSONTagValue(testCaseJson, 'externalId'),
                                    self.GetJSONTagValue(testCaseJson, 'oldId'),
                                    self.GetJSONTagValue(testCaseJson, 'lastUpdaterId'),
                                    self.GetJSONTagValue(testCaseJson, 'isComplex'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseSequence'),
                                    self.GetJSONTagValue(testCaseJson, 'projectName'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseId'),
                                    self.GetJSONTagValue(testCaseJson, 'customProcessedProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'versionNumber'),
                                    self.GetJSONTagValue(testCaseJson, 'automated'),
                                    self.GetJSONTagValue(testCaseJson, 'creationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'name'),
                                    customFieldValueListObj,
                                    self.GetJSONTagValue(testCaseJson, 'creatorId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseShared'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreatedBy'))

            tcrTreeTestCaseObj = CTcrTreeTestCase(self.GetJSONTagValue(testResult, 'lastModifiedOn'),
                                                  self.GetJSONTagValue(testResult, 'releaseName'),
                                                  self.GetJSONTagValue(testResult, 'stateFlag'),
                                                  self.GetJSONTagValue(testResult, 'projectIdParam'),
                                                  self.GetJSONTagValue(testResult, 'tcrCatalogTreeId'),
                                                  self.GetJSONTagValue(testResult, 'projectId'),
                                                  self.GetJSONTagValue(testResult, 'orderId'),
                                                  self.GetJSONTagValue(testResult, 'original'),
                                                  testCaseObj,
                                                  self.GetJSONTagValue(testResult, 'releaseId'),
                                                  self.GetJSONTagValue(testResult, 'versionNumber'),
                                                  self.GetJSONTagValue(testResult, 'isDerivedFromBDD'),
                                                  self.GetJSONTagValue(testResult, 'maxVersionNumber'),
                                                  self.GetJSONTagValue(testResult, 'id'),
                                                  self.GetJSONTagValue(testResult, 'revision'))
            testCaseList.append(tcrTreeTestCaseObj)
        return testCaseList

    def createPhaseTestPlanbyTestCaseIds(self, cyclePhaseId, tctIdList):

        valueList = []
        valueDict = {}

        for tctId in tctIdList:
            valueList.append(tctId.id)
        valueDict["ids"] = valueList
        values = json.dumps(valueDict)
        cyclePhaseAssignmentTreeInfo    = self.getCyclePhaseTreeIdForAssignement(cyclePhaseId)

        rep = {"CYCLE_PHASE_ID": str(cyclePhaseId), "ASSIGNMENT_TREE_ID": str(cyclePhaseAssignmentTreeInfo.id)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], CREATE_PHASE_TEST_PLAN_BY_SEARCHID)

        postURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).post(postURL, values)

        sendLogToStdout("createPhaseTestPlanbyTestCaseIds: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: createPhaseTestPlanbyTestCaseIds: HTTP error %s is received in response for POST request : %s" % (
                response.status_code, postURL))
            return None, None

        return True

    def createPhaseTestPlanbyTreeId(self, cyclePhaseId, tctTreeIdList):

        values = json.dumps(tctTreeIdList)
        cyclePhaseAssignmentTreeInfo    = self.getCyclePhaseTreeIdForAssignement(cyclePhaseId)

        rep = {"CYCLE_PHASE_ID": str(cyclePhaseId), "ASSIGNMENT_TREE_ID": str(cyclePhaseAssignmentTreeInfo.id)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], CREATE_PHASE_TEST_PLAN_BY_TREEID)

        postURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).post(postURL, values)

        sendLogToStdout("createPhaseTestPlanbyTreeId: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: createPhaseTestPlanbyTreeId: HTTP error %s is received in response for POST request : %s" % (
                response.status_code, postURL))
            return None, None

        return True

    def getCyclePhase(self, cyclePhaseId):
        '''
        Returns cycle Phase based on cyclePhaseId
        :param cyclePhaseId:
        :return:
        '''
        cyclePhaseRet = None
        for cyclePhase in self._AutomationCycleDetail.cyclePhases:
            if cyclePhaseId == cyclePhase.id:
                cyclePhaseRet = cyclePhase
        return cyclePhaseRet

    #def getCyclePhaseInfoByProjectIdReleaseId(self, projectId, releaseId, cycleId, cyclePhaseName):


    def updateCyclePhaseValuesWithCurrentDate(self, cycleId, newCyclePhaseName, cyclePhaseId):

        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        EndDateEpochTimeinMS = StartDateEpochTimeinMS + 86400000

        cyclePhaseObj = self.getCyclePhase(cyclePhaseId)
        putURL = self._zephyrBaseURL + UPDATE_CYCLE_PHASE_VAL.replace("CYCLE_ID", str(cycleId))

        values = cyclePhaseObj.GetJSONPayloadForUpdation(newCyclePhaseName, StartDateEpochTimeinMS, EndDateEpochTimeinMS, StartDateEpochTimeinMS)

        response = (self.getZephyrSession().put(putURL, values))

        sendLogToStdout("updateCyclePhaseValuesWithCurrentDate: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: updateCyclePhaseValuesWithCurrentDate: HTTP error %s is received in response for PUT request : %s" % (response.status_code, putURL))
            return False

        self.UpdateAutomationCycleDetailContext()
        return True

    def GetAllExecutionsContextForAllPhaseTCRID(self, cyclePhaseId, releaseId, testCaseInfoDict, excutionDetailList):

        testCaseCount = 0
        for testCaseID, testCaseInfo in testCaseInfoDict.iteritems():

            # Get Test case count by CycleTcrCatalogTreeID
            testCaseCount += self.getTestCaseCountByCycleTcrCatalogTreeId(testCaseInfo.id, releaseId)

        self.GetAllExecutionsContextforCurrentUserByCriteria(cyclePhaseId, releaseId, testCaseCount, excutionDetailList)


    def getTestCaseSteps(self, testCaseZephyrId, isfetchstepversion = True):
        '''
        :param testCaseZephyrId:
        :param testCaseVersionId:
        :param isfetchstepversion:
        :return:
        '''

        testCaseExecutionInfoObj    = None
        testStepsListObj            = []
        rep = {"TEST_CASE_ZEPHYR_ID": str(testCaseZephyrId), "IS_FETCH_VERSION": "true" if isfetchstepversion is True else "false", "TEST_CASE_VERION_ID": str(testCaseZephyrId)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], FETCH_TEST_CASE_STEPS)

        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("getTestCaseSteps: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                "ERROR: getTestCaseSteps: HTTP error %s is received in response for GET request : %s" % (
                response.status_code, requestURL))
            return testCaseExecutionInfoObj

        responseJson    = response.json()

        if bool(responseJson) is False:
            return testCaseExecutionInfoObj;

        testCaseStepsJson   = responseJson["steps"]

        for testSteps in testCaseStepsJson:

            testStepsObj    = CTestSteps(self.GetJSONTagValue(testSteps, 'id'),
                                         self.GetJSONTagValue(testSteps, 'localId'),
                                         self.GetJSONTagValue(testSteps, 'orderId'),
                                         self.GetJSONTagValue(testSteps, 'step'),
                                         self.GetJSONTagValue(testSteps, 'data'),
                                         self.GetJSONTagValue(testSteps, 'result'))
            testStepsListObj.append(testStepsObj)

        testCaseExecutionInfoObj = CTestCaseExecutionInfo(self.GetJSONTagValue(responseJson, 'id'),
                                                           self.GetJSONTagValue(responseJson, 'tcId'),
                                                           self.GetJSONTagValue(responseJson, 'releaseId'),
                                                           self.GetJSONTagValue(responseJson, 'maxId'),
                                                           testStepsListObj,
                                                           self.GetJSONTagValue(responseJson, 'lastModificationDate'),
                                                           self.GetJSONTagValue(responseJson, 'lastModifiedBy'))

        return testCaseExecutionInfoObj

    def GetAllExecutionsContextforCurrentUserByCriteria(self, cyclePhaseId, releaseId, testCaseCount, excutionDetailList):
        '''
        Fetch all executions by cyclePhaseId and releaseID
        :param cyclePhaseId:
        :param releaseId:
        :return:
        '''
        rep = {"RELEASE_ID": str(releaseId), "CYCLE_PHASE_ID": str(cyclePhaseId), "TESTER_ID": str(self._userId), "PAGE_SIZE": str(testCaseCount)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], GET_ALL_EXECUTION_BY_CRITERIA)

        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("GetAllExecutionsContextforCurrentUserByCriteria: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: GetAllExecutionsContextforCurrentUserByCriteria: HTTP error %s is received in response for GET request : %s" % (response.status_code, requestURL))
            return False

        responseJson = response.json()

        jsonContent  = responseJson["results"]

        for testResult in jsonContent:

            testCaseJson = testResult["tcrTreeTestcase"]["testcase"]
            customFieldValueJson = testCaseJson["customFieldValues"]
            customFieldValueListObj = []

            for customFieldValueItem in customFieldValueJson:
                customFieldValueObj = CTestCaseCustomFieldValue(
                    self.GetJSONTagValue(customFieldValueItem, 'displayName'),
                    self.GetJSONTagValue(customFieldValueItem, 'value'),
                    self.GetJSONTagValue(customFieldValueItem, 'testcaseVersionId'),
                    self.GetJSONTagValue(customFieldValueItem, 'pickListValue'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldName'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldTypeMetadata'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldId'),
                    self.GetJSONTagValue(customFieldValueItem, 'id'))
                customFieldValueListObj.append(customFieldValueObj)

            testCaseObj = CTestCase(self.GetJSONTagValue(testCaseJson, 'lastModifiedOn'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIds'),
                                    self.GetJSONTagValue(testCaseJson, 'customFieldProcessed'),
                                    self.GetJSONTagValue(testCaseJson, 'tag'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIdsNew'),
                                    self.GetJSONTagValue(testCaseJson, 'tcCreationData'),
                                    self.GetJSONTagValue(testCaseJson, 'customProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'id'),
                                    self.GetJSONTagValue(testCaseJson, 'description'),
                                    self.GetJSONTagValue(testCaseJson, 'estimatedTime'),
                                    self.GetJSONTagValue(testCaseJson, 'projectId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseType'),
                                    self.GetJSONTagValue(testCaseJson, 'automationDefault'),
                                    self.GetJSONTagValue(testCaseJson, 'comments'),
                                    self.GetJSONTagValue(testCaseJson, 'priority'),
                                    self.GetJSONTagValue(testCaseJson, 'externalId'),
                                    self.GetJSONTagValue(testCaseJson, 'oldId'),
                                    self.GetJSONTagValue(testCaseJson, 'lastUpdaterId'),
                                    self.GetJSONTagValue(testCaseJson, 'isComplex'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseSequence'),
                                    self.GetJSONTagValue(testCaseJson, 'projectName'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseId'),
                                    self.GetJSONTagValue(testCaseJson, 'customProcessedProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'versionNumber'),
                                    self.GetJSONTagValue(testCaseJson, 'automated'),
                                    self.GetJSONTagValue(testCaseJson, 'creationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'name'),
                                    customFieldValueListObj,
                                    self.GetJSONTagValue(testCaseJson, 'creatorId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseShared'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreatedBy'))

            tcrTreeTestCaseJson = testResult["tcrTreeTestcase"]
            tcrTreeTestCaseObj = CTcrTreeTestCase(self.GetJSONTagValue(tcrTreeTestCaseJson, 'lastModifiedOn'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'releaseName'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'stateFlag'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'projectIdParam'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'tcrCatalogTreeId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'projectId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'orderId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'original'),
                                                  testCaseObj,
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'releaseId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'versionNumber'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'isDerivedFromBDD'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'maxVersionNumber'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'id'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'revision'))
            executionKeys = testResult.keys()
            lastTestResultObj = None
            if "lastTestResult" in executionKeys:
                lastTestResultJson = testResult["lastTestResult"]
                lastTestResultObj = CLastTestResult(self.GetJSONTagValue(lastTestResultJson, 'id'), self.GetJSONTagValue(lastTestResultJson, 'executionDate'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'execDate'), self.GetJSONTagValue(lastTestResultJson, 'executionStatus'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'testerId'), self.GetJSONTagValue(lastTestResultJson, 'releaseTestScheduleId'))
            else:
                lastTestResultObj = CLastTestResult(None, None, None, None, None, None)

            defectKeys  = testResult.keys()
            defectList = []
            if "defects" in defectKeys:
                defectJson  = testResult["defects"]

                for defectItem in defectJson:
                    defectDetail = CDefectDetail(self.GetJSONTagValue(defectItem, 'id'), self.GetJSONTagValue(defectItem, 'bugId'),
                                                    self.GetJSONTagValue(defectItem, 'externalId'), self.GetJSONTagValue(defectItem, 'description'),
                                                    self.GetJSONTagValue(defectItem, 'createdDate'), self.GetJSONTagValue(defectItem, 'status'),
                                                    self.GetJSONTagValue(defectItem, 'priority'), self.GetJSONTagValue(defectItem, 'state'),
                                                    self.GetJSONTagValue(defectItem, 'dtsId'), self.GetJSONTagValue(defectItem, 'category'),
                                                    self.GetJSONTagValue(defectItem, 'testResults'))
                    defectList.append(defectDetail)

            testCaseStepObj = self.getTestCaseSteps(testCaseObj.id)

            executionDetailObj   = CExecutionDetail(self.GetJSONTagValue(testResult, 'status'), self.GetJSONTagValue(testResult, 'lastModifiedOn'),
                                                    self.GetJSONTagValue(testResult, 'attachementCount'), tcrTreeTestCaseObj,
                                                    self.GetJSONTagValue(testResult, 'testerId'), defectList,
                                                    self.GetJSONTagValue(testResult, 'assignmentDate'),
                                                    self.GetJSONTagValue(testResult, 'cyclePhaseId'),
                                                    self.GetJSONTagValue(testResult, 'id'), testCaseStepObj)
            excutionDetailList.append(executionDetailObj)

        return True

    def GetAllExecutionsContextByCriteria(self, cyclePhaseId, releaseId, testCaseCount, excutionDetailList):
        '''
        Fetch all executions by cyclePhaseId and releaseID
        :param cyclePhaseId:
        :param releaseId:
        :return:
        '''
        rep = {"RELEASE_ID": str(releaseId), "CYCLE_PHASE_ID": str(cyclePhaseId), "PAGE_SIZE": str(testCaseCount)}
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], GET_ALL_EXECUTION)

        requestURL = self._zephyrBaseURL + finalPathURL
        response = (self.getZephyrSession()).get(requestURL)

        sendLogToStdout("GetAllExecutionsContextByCriteria: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout("ERROR: GetAllExecutionsContextByCriteria: HTTP error %s is received in response for GET request : %s" % (response.status_code, requestURL))
            return False

        responseJson = response.json()

        jsonContent  = responseJson["results"]

        for testResult in jsonContent:
            testCaseJson = testResult["tcrTreeTestcase"]["testcase"]
            customFieldValueJson = testCaseJson["customFieldValues"]
            customFieldValueListObj = []

            for customFieldValueItem in customFieldValueJson:
                customFieldValueObj = CTestCaseCustomFieldValue(
                    self.GetJSONTagValue(customFieldValueItem, 'displayName'),
                    self.GetJSONTagValue(customFieldValueItem, 'value'),
                    self.GetJSONTagValue(customFieldValueItem, 'testcaseVersionId'),
                    self.GetJSONTagValue(customFieldValueItem, 'pickListValue'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldName'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldTypeMetadata'),
                    self.GetJSONTagValue(customFieldValueItem, 'fieldId'),
                    self.GetJSONTagValue(customFieldValueItem, 'id'))
                customFieldValueListObj.append(customFieldValueObj)

            testCaseObj = CTestCase(self.GetJSONTagValue(testCaseJson, 'lastModifiedOn'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIds'),
                                    self.GetJSONTagValue(testCaseJson, 'customFieldProcessed'),
                                    self.GetJSONTagValue(testCaseJson, 'tag'),
                                    self.GetJSONTagValue(testCaseJson, 'requirementIdsNew'),
                                    self.GetJSONTagValue(testCaseJson, 'tcCreationData'),
                                    self.GetJSONTagValue(testCaseJson, 'customProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'id'),
                                    self.GetJSONTagValue(testCaseJson, 'description'),
                                    self.GetJSONTagValue(testCaseJson, 'estimatedTime'),
                                    self.GetJSONTagValue(testCaseJson, 'projectId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseType'),
                                    self.GetJSONTagValue(testCaseJson, 'automationDefault'),
                                    self.GetJSONTagValue(testCaseJson, 'comments'),
                                    self.GetJSONTagValue(testCaseJson, 'priority'),
                                    self.GetJSONTagValue(testCaseJson, 'externalId'),
                                    self.GetJSONTagValue(testCaseJson, 'oldId'),
                                    self.GetJSONTagValue(testCaseJson, 'lastUpdaterId'),
                                    self.GetJSONTagValue(testCaseJson, 'isComplex'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseSequence'),
                                    self.GetJSONTagValue(testCaseJson, 'projectName'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseId'),
                                    self.GetJSONTagValue(testCaseJson, 'customProcessedProperties'),
                                    self.GetJSONTagValue(testCaseJson, 'versionNumber'),
                                    self.GetJSONTagValue(testCaseJson, 'automated'),
                                    self.GetJSONTagValue(testCaseJson, 'creationDate'),
                                    self.GetJSONTagValue(testCaseJson, 'name'),
                                    customFieldValueListObj,
                                    self.GetJSONTagValue(testCaseJson, 'creatorId'),
                                    self.GetJSONTagValue(testCaseJson, 'testcaseShared'),
                                    self.GetJSONTagValue(testCaseJson, 'versionCreatedBy'))

            tcrTreeTestCaseJson = testResult["tcrTreeTestcase"]
            tcrTreeTestCaseObj = CTcrTreeTestCase(self.GetJSONTagValue(tcrTreeTestCaseJson, 'lastModifiedOn'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'releaseName'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'stateFlag'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'projectIdParam'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'tcrCatalogTreeId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'projectId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'orderId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'original'),
                                                  testCaseObj,
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'releaseId'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'versionNumber'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'isDerivedFromBDD'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'maxVersionNumber'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'id'),
                                                  self.GetJSONTagValue(tcrTreeTestCaseJson, 'revision'))
            executionKeys = testResult.keys()
            lastTestResultObj = None
            if "lastTestResult" in executionKeys:
                lastTestResultJson = testResult["lastTestResult"]
                lastTestResultObj = CLastTestResult(self.GetJSONTagValue(lastTestResultJson, 'id'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'executionDate'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'execDate'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'executionStatus'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'testerId'),
                                                    self.GetJSONTagValue(lastTestResultJson, 'releaseTestScheduleId'))
            else:
                lastTestResultObj = CLastTestResult(None, None, None, None, None, None)

            defectKeys = testResult.keys()
            defectList = []
            if "defects" in defectKeys:
                defectJson = testResult["defects"]

                for defectItem in defectJson:
                    defectDetail = CDefectDetail(self.GetJSONTagValue(defectItem, 'id'),
                                                 self.GetJSONTagValue(defectItem, 'bugId'),
                                                 self.GetJSONTagValue(defectItem, 'externalId'),
                                                 self.GetJSONTagValue(defectItem, 'description'),
                                                 self.GetJSONTagValue(defectItem, 'createdDate'),
                                                 self.GetJSONTagValue(defectItem, 'status'),
                                                 self.GetJSONTagValue(defectItem, 'priority'),
                                                 self.GetJSONTagValue(defectItem, 'state'),
                                                 self.GetJSONTagValue(defectItem, 'dtsId'),
                                                 self.GetJSONTagValue(defectItem, 'category'),
                                                 self.GetJSONTagValue(defectItem, 'testResults'))
                    defectList.append(defectDetail)

            testCaseStepObj = self.getTestCaseSteps(testCaseObj.id)

            executionDetailObj = CExecutionDetail(self.GetJSONTagValue(testResult, 'status'),
                                                  self.GetJSONTagValue(testResult, 'lastModifiedOn'),
                                                  self.GetJSONTagValue(testResult, 'attachementCount'),
                                                  tcrTreeTestCaseObj,
                                                  self.GetJSONTagValue(testResult, 'testerId'),
                                                  defectList,
                                                  self.GetJSONTagValue(testResult, 'assignmentDate'),
                                                  self.GetJSONTagValue(testResult, 'cyclePhaseId'),
                                                  self.GetJSONTagValue(testResult, 'id'),
                                                  testCaseStepObj,
                                                  lastTestResultObj,
                                                  self.GetJSONTagValue(testResult, 'versionId'),
                                                  self.GetJSONTagValue(testResult, 'executedBy'),
                                                  self.GetJSONTagValue(testResult, 'actualTime'))

            excutionDetailList.append(executionDetailObj)

        return True

    def updateExecutionResultByZephyrID(self, zephyrTicketId, resultStatus, testDuration, excutionDetailList, comment = None):
        '''
        Update Execution result for given zephyr ticket ID
        :param zephyrTicketId:
        :param resultStatus:
        :param testDuration:
        :return:
        '''
        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        IsTicketFound = False

        sendLogToStdout("updateExecutionResultByZephyrID: zephyrTicketId : %s" % zephyrTicketId)

        for execution in excutionDetailList:
            if ( execution.tcrTreeTestCaseObj.testcaseObj.testcaseid == zephyrTicketId):
                values = None
                IsTicketFound = True
                if comment is None:
                    values = json.dumps({})
                else:
                    values = json.dumps({"notes": comment})
                rep = {"EXECUTION_ID": str(execution.id), "EXECUTION_RESULT": str(resultStatus), "TESTER_ID": str(self._userId)}
                rep = dict((re.escape(k), v) for k, v in rep.iteritems())
                pattern = re.compile("|".join(rep.keys()))
                finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], UPDATE_EXECUTION_RESULT)

                putHttpURL = self._zephyrBaseURL + finalPathURL
                response = (self.getZephyrSession()).put(putHttpURL, values)

                sendLogToStdout("updateExecutionResultByZephyrID: response.status_code : %s" % response.status_code)
                if (response.status_code != 200):
                    sendLogToStdout("ERROR updateExecutionResultByZephyrID: HTTP error %s is received in response for PUT request : %s" %(response.status_code, putHttpURL))
                    return False

                jsonContent = response.json()

                sendLogToStdout("updateExecutionResultByZephyrID : json Response %s" %jsonContent)
                break

        self.UpdateAutomationCycleDetailContext()
        return IsTicketFound

    def updateExecutionResultByExternalID(self, externalId, resultStatus, testDuration, executionDetailList, comment = None):
        '''
        Update Execution result for given zephyr ticket ID
        :param zephyrTicketId:
        :param resultStatus:
        :param testDuration:
        :return:
        '''
        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        IsExternalIdFound = False

        if (externalId is None) or (len(str(externalId).encode("ascii")) <= 0):
            sendLogToStdout("ERROR updateExecutionResultByExternalID: external ID is None for Step ID : %s" % StepId)
            return IsExternalIdFound

        sendLogToStdout("updateExecutionResultByExternalID: ExternalId : %s" %externalId)

        for execution in executionDetailList:
            if ( execution.tcrTreeTestCaseObj.testcaseObj.externalId == externalId):
                values = None
                IsExternalIdFound = True
                if comment is None:
                    values = json.dumps({})
                else:
                    values = json.dumps({"notes": comment})

                rep = {"EXECUTION_ID": str(execution.id), "EXECUTION_RESULT": str(resultStatus), "TESTER_ID": str(self._userId)}
                rep = dict((re.escape(k), v) for k, v in rep.iteritems())
                pattern = re.compile("|".join(rep.keys()))
                finalPathURL = pattern.sub(lambda m: rep[re.escape(m.group(0))], UPDATE_EXECUTION_RESULT)

                putHttpURL = self._zephyrBaseURL + finalPathURL
                response = (self.getZephyrSession()).put(putHttpURL, values)

                sendLogToStdout("updateExecutionResultByExternalID: response.status_code : %s" % response.status_code)
                if (response.status_code != 200):
                    sendLogToStdout("ERROR: updateExecutionResultByExternalID: HTTP error %s is received in response for PUT request : %s" % (response.status_code, putHttpURL))
                    return False

                jsonContent = response.json()

                sendLogToStdout("updateExecutionResultByExternalID: updateExecutionResult : json Response %s" %jsonContent)
                break

        self.UpdateAutomationCycleDetailContext()
        return IsExternalIdFound

    def test_update_execution_status(self, cyclePhaseId, executionDetailList):
        '''
        Test Code
        :param zephyrTicketId:
        :param resultStatus:
        :param testDuration:
        :return:
        '''

        resultStatus = [1, 2, 3, 4]  # PASS,FAIL,WIP,BLOCKED

        for execution in executionDetailList:

            status = random.choice(resultStatus)

            numberOfTestSteps = len(execution.testStepObj.steps)

            for stepId in range(0, numberOfTestSteps):

                self.updateExecutionTestCaseStepByZephyrID(execution.tcrTreeTestCaseObj.testcaseObj.testcaseid,
                                                           stepId, status, cyclePhaseId, executionDetailList)
                #self.updateExecutionTestCaseStepByExternalID(execution.tcrTreeTestCaseObj.testcaseObj.externalId,
                #                                           stepId, status, cyclePhaseId, executionDetailList)

            #self.updateExecutionResultByExternalID(execution.tcrTreeTestCaseObj.testcaseObj.externalId, status, 100, executionDetailList)

            self.updateExecutionResultByZephyrID(execution.tcrTreeTestCaseObj.testcaseObj.testcaseid, status, 100, executionDetailList)

    def updateExecutionTestCaseStepByZephyrID(self, zephyrTicketId, StepId, testStepStatus,
                                              cyclePhaseId,executionDetailList, comment = None, attachmentCount = 0):
        '''
        Update Execution result for given zephyr ticket ID
        :param zephyrTicketId:
        :param resultStatus:
        :param testDuration:
        :return:
        '''
        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        IsTicketFound = False

        sendLogToStdout("updateExecutionTestCaseStepByZephyrID: zephyrTicketId : %s" % zephyrTicketId)

        for execution in executionDetailList:
            if ( execution.tcrTreeTestCaseObj.testcaseObj.testcaseid == zephyrTicketId):

                testStepId = None
                testStepIdList = []
                for stepItem in execution.testStepObj.steps:
                    testStepIdList.append(stepItem.localId)

                if len(testStepIdList) > 0 :
                    testStepIdList.sort()

                testStepId = testStepIdList[StepId -  1]
                IsTicketFound = True
                if comment is None:
                    values = json.dumps([{"testStepId": testStepId, "executionDate": StartDateEpochTimeinMS,
                                         "cyclePhaseId": cyclePhaseId,
                                         "releaseTestScheduleId": execution.id, "status": testStepStatus,
                                         "attachmentCount": attachmentCount}])
                else:
                    values = json.dumps([{"testStepId": testStepId, "executionDate": StartDateEpochTimeinMS,
                                         "cyclePhaseId": cyclePhaseId, "comment": comment,
                                         "releaseTestScheduleId": execution.id, "status": testStepStatus,
                                         "attachmentCount": attachmentCount}])

                postHttpURL = self._zephyrBaseURL + UPDATE_TEST_STEP_RESULT
                response = (self.getZephyrSession()).post(postHttpURL, values)

                sendLogToStdout("updateExecutionTestCaseStepByZephyrID: response.status_code : %s" % response.status_code)
                if (response.status_code != 200):
                    sendLogToStdout("ERROR updateExecutionTestCaseStepByZephyrID: HTTP error %s is received in response for PUT request : %s" %(response.status_code, postHttpURL))
                    return False

                jsonContent = response.json()

                sendLogToStdout("updateExecutionTestCaseStepByZephyrID : json Response %s" %jsonContent)
                break
        return IsTicketFound

    def updateExecutionTestCaseStepByExternalID(self, externalId, StepId, testStepStatus,
                                              cyclePhaseId,executionDetailList, comment = None, attachmentCount = 0):
        '''
        Update Execution result for given zephyr ticket ID
        :param zephyrTicketId:
        :param resultStatus:
        :param testDuration:
        :return:
        '''
        currentEpochTime = time.time()
        StartDateEpochTimeinMS = int(currentEpochTime * 1000)
        IsTicketFound = False

        if (externalId is None) or (len(str(externalId).encode("ascii")) <= 0):
            sendLogToStdout("ERROR updateExecutionTestCaseStepByExternalID: external ID is None for Step ID : %s" %StepId)
            return IsTicketFound

        sendLogToStdout("updateExecutionTestCaseStepByExternalID: externalId : %s" % externalId)

        for execution in executionDetailList:

            if (execution.tcrTreeTestCaseObj.testcaseObj.externalId == externalId):
                IsTicketFound = True
                testStepIdList = []
                for stepItem in execution.testStepObj.steps:
                    testStepIdList.append(stepItem.localId)

                if len(testStepIdList) > 0:
                    testStepIdList.sort()

                testStepId = testStepIdList[StepId - 1]

                if comment is None:
                    values = json.dumps([{"testStepId": testStepId, "executionDate": StartDateEpochTimeinMS,
                                         "cyclePhaseId": cyclePhaseId,
                                         "releaseTestScheduleId": execution.id, "status": testStepStatus,
                                         "attachmentCount": attachmentCount}])
                else:
                    values = json.dumps([{"testStepId": testStepId, "executionDate": StartDateEpochTimeinMS,
                                         "cyclePhaseId": cyclePhaseId, "comment": comment,
                                         "releaseTestScheduleId": execution.id, "status": testStepStatus,
                                         "attachmentCount": attachmentCount}])

                postHttpURL = self._zephyrBaseURL + UPDATE_TEST_STEP_RESULT
                response = (self.getZephyrSession()).post(postHttpURL, values)

                sendLogToStdout("updateExecutionTestCaseStepByExternalID: response.status_code : %s" % response.status_code)
                if (response.status_code != 200):
                    sendLogToStdout("ERROR updateExecutionTestCaseStepByExternalID: HTTP error %s is received in response for PUT request : %s" %(response.status_code, postHttpURL))
                    return False

                jsonContent = response.json()

                sendLogToStdout("updateExecutionTestCaseStepByExternalID : json Response %s" %jsonContent)
                break
        return IsTicketFound

    def generateZephyrMetrics(self):

        projList    = []
        for projectInfo in self._completeProjectInfoList.projectList:
            projDict    = {}
            releaseList = []
            projDict["PROJECT_NAME"] = str(projectInfo.projectInfo.name)
            jsonFileName = ZEPHYR_DATA_FILE_LOC + "ZEPHYR_PROJECT_INFO/" +  str(projectInfo.projectInfo.name).replace(" ","") + ".json"

            for relItem in projectInfo.releaseListDetail:
                relDict = {}
                cycleList = []
                relDict["name"] = str(relItem.releaseInfo.name)

                testRepoList = self.GetTestRepositoryMetricsByReleaseID(projectInfo.projectInfo.name, relItem.releaseInfo.name, relItem.releaseInfo.id, self._tagList)
                relDict["testRepoMetric"] = testRepoList
                if relItem.releaseCycle is not None:
                    for cycleItem in relItem.releaseCycle:
                        cycleDict = {}
                        cyclePhaseList = []
                        for cyclePhase in cycleItem.cyclePhases:
                            cyclePhaseDict = {}
                            tcrCatalogTreeId = cyclePhase.tcrCatalogTreeId
                            cyclePhaseId     = cyclePhase.id
                            zephyrCyclePhaseMetric = self.GetAutomationExecutionMetricsByCriteria(relItem.releaseInfo.id, tcrCatalogTreeId, cyclePhaseId, cyclePhase.phaseStartDate, cyclePhase.phaseStartDate)
                            cyclePhaseDict["CyclePhaseName"]        = cyclePhase.name
                            cyclePhaseDict["Passed"]                = zephyrCyclePhaseMetric.passedCount
                            cyclePhaseDict["Failed"]                = zephyrCyclePhaseMetric.failedCount
                            cyclePhaseDict["Blocked"]               = zephyrCyclePhaseMetric.blockedCount
                            cyclePhaseDict["WIP"]                   = zephyrCyclePhaseMetric.WipCount
                            cyclePhaseDict["Unexecuted"]            = zephyrCyclePhaseMetric.TotalTestCases - (zephyrCyclePhaseMetric.passedCount + zephyrCyclePhaseMetric.failedCount + zephyrCyclePhaseMetric.blockedCount + zephyrCyclePhaseMetric.WipCount)
                            cyclePhaseDict["Total"]                 = zephyrCyclePhaseMetric.TotalTestCases
                            cyclePhaseDict["newDefectCount"]        = zephyrCyclePhaseMetric.newDefectCount
                            cyclePhaseDict["existingDefectCount"]   = zephyrCyclePhaseMetric.existingDefectCount
                            cyclePhaseList.append(cyclePhaseDict)
                        cycleDict["name"] = str(cycleItem.name)
                        cycleDict["CyclePhases"]    =  cyclePhaseList
                        cycleList.append(cycleDict)
                relDict["CYCLES"] = cycleList
                releaseList.append(relDict)
            projDict["RELEASES"] = releaseList
            projList.append(projDict)
            #Create test Repo JSON
            file = open(jsonFileName, "w")
            json.dump(projDict, file)
            file.close()
            time.sleep(60)

    def getTestCaseListByTag(self, releaseId, tagName):

        totalTestCaseList, testCaseCount = self.getTestCasesByReleaseId(releaseId)
        testCaseList, testCaseCounyByTag = self.getTestCaseCountByTag(totalTestCaseList, str(tagName))
        return testCaseCounyByTag

    def GetTestRepositoryMetricsByReleaseID(self, projectName, releaseName, releaseId, tagList):

        dictData = {}
        testRepoMetricList = []

        totalTestCaseList, testCaseCount = self.getTestCasesByReleaseId(releaseId)
        dictData['Total_Test_Cases'] = testCaseCount

        for tags in tagList:
            testCaseList, testCaseCounyByTag = self.getTestCaseCountByTag(totalTestCaseList, str(tags))
            dictData[tags] = testCaseCounyByTag
        dictData["ReleaseName"] = releaseName


        currentTestRepoJSON = self.getTestRepoJson(dictData)

        jsonFileName = ZEPHYR_DATA_FILE_LOC + "ZEPHYR_PROJECT_INFO/" + projectName.replace(" ", "") + ".json"

        if os.path.isfile(jsonFileName):

            with open(jsonFileName, 'r') as f:
                jsonFileContent = json.loads(f.read())
                f.close()
            releaseList = jsonFileContent['RELEASES']

            for relItem in releaseList:
                if str(relItem["name"]) == releaseName:
                    testRepoMetricList = relItem["testRepoMetric"]
                    break

        latestTestRepoMetric = []
        if len(testRepoMetricList) > 0:
            sortedList = []
            pattern = "%d-%m-%Y"
            sortedList = sorted(testRepoMetricList, key=lambda k: int(time.mktime(time.strptime(k['Date'], pattern))))

            latestTestRepoMetric = sortedList[-1]

            isAllMetricsAreSame             = True

            for tags in tagList:
                isAllMetricsAreSame = isAllMetricsAreSame & (int(latestTestRepoMetric[tags]) == int(currentTestRepoJSON[tags]))

            if isAllMetricsAreSame is True:
                sendLogToStdout("All the metrics are same")
            else:
                testRepoMetricList.append(currentTestRepoJSON)
        else:
            testRepoMetricList.append(currentTestRepoJSON)

        return testRepoMetricList

    def getTestRepoJson(self, dictData):

        tempData = {}
        now = datetime.datetime.now()

        for key, value in dictData.iteritems():
            if key == "ReleaseName":
                continue
            tempData[key] = value

        tempData['Date'] = "%s-%s-%s" % (now.day, now.month, now.year)
        return tempData

    def getTestCasesByReleaseId(self, releaseID):

        testRepositoryTCInfo = CTestRepositoryTestCaseInfo()
        requestURL = self._zephyrBaseURL + GET_TEST_COUNT_BY_REL_ID.replace("RELEASE_ID", str(releaseID))
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getTreeIdsByReleaseId: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                        "ERROR: getTreeIdsByReleaseId: HTTP error %s is received in response for GET request : %s" % (
                response.status_code, requestURL))
            return None

        jsonContent = response.json()

        for treeIdInfo in jsonContent:

            jsonContent = self.getTestCaseListByTreeId(treeIdInfo['treeId'])

            if (jsonContent['resultSize'] > 0) :
                for testCase in jsonContent['results']:
                    testRepositoryTCInfo.append(self.getTestCasesObject(testCase))
        return testRepositoryTCInfo , testRepositoryTCInfo.count()

    def getTestCaseListByTreeId(self, treeId):

        requestURL = self._zephyrBaseURL + GET_TEST_CASES_BY_TREEID.replace("TREE_ID", str(treeId))
        response = (self.getZephyrSession().get(requestURL))

        sendLogToStdout("getTestCaseListByTreeId: response.status_code : %s" % response.status_code)
        if (response.status_code != 200):
            sendLogToStdout(
                "ERROR: getTestCaseListByTreeId: HTTP error %s is received in response for GET request : %s" % (
                    response.status_code, requestURL))
            return None

        jsonContent = response.json()
        return jsonContent

    def getTestCaseCountByTag(self, testRepositoryTCInfo, tagName):

        testCaseList, count = testRepositoryTCInfo.countByTags(tagName)
        return testCaseList, count

    def getTestCasesObject(self, jsonContent):
        '''
        Get All test cases scheduled in cycle Phase ID
        :param cyclePhaseId:
        :return:
        '''

        testCaseJson = jsonContent["testcase"]
        customFieldValueJson = testCaseJson["customFieldValues"]
        customFieldValueListObj = []

        for customFieldValueItem in customFieldValueJson:
            customFieldValueObj = CTestCaseCustomFieldValue(self.GetJSONTagValue(customFieldValueItem, 'displayName'),
                                                            self.GetJSONTagValue(customFieldValueItem, 'value'),
                                                            self.GetJSONTagValue(customFieldValueItem,
                                                                                 'testcaseVersionId'),
                                                            self.GetJSONTagValue(customFieldValueItem, 'pickListValue'),
                                                            self.GetJSONTagValue(customFieldValueItem, 'fieldName'),
                                                            self.GetJSONTagValue(customFieldValueItem,
                                                                                 'fieldTypeMetadata'),
                                                            self.GetJSONTagValue(customFieldValueItem, 'fieldId'),
                                                            self.GetJSONTagValue(customFieldValueItem, 'id'))
            customFieldValueListObj.append(customFieldValueObj)

        testCaseObj = CTestCase(self.GetJSONTagValue(testCaseJson, 'lastModifiedOn'),
                                self.GetJSONTagValue(testCaseJson, 'versionCreationDate'),
                                self.GetJSONTagValue(testCaseJson, 'requirementIds'),
                                self.GetJSONTagValue(testCaseJson, 'customFieldProcessed'),
                                self.GetJSONTagValue(testCaseJson, 'tag'),
                                self.GetJSONTagValue(testCaseJson, 'requirementIdsNew'),
                                self.GetJSONTagValue(testCaseJson, 'tcCreationData'),
                                self.GetJSONTagValue(testCaseJson, 'customProperties'),
                                self.GetJSONTagValue(testCaseJson, 'id'),
                                self.GetJSONTagValue(testCaseJson, 'description'),
                                self.GetJSONTagValue(testCaseJson, 'estimatedTime'),
                                self.GetJSONTagValue(testCaseJson, 'projectId'),
                                self.GetJSONTagValue(testCaseJson, 'testcaseType'),
                                self.GetJSONTagValue(testCaseJson, 'automationDefault'),
                                self.GetJSONTagValue(testCaseJson, 'comments'),
                                self.GetJSONTagValue(testCaseJson, 'priority'),
                                self.GetJSONTagValue(testCaseJson, 'externalId'),
                                self.GetJSONTagValue(testCaseJson, 'oldId'),
                                self.GetJSONTagValue(testCaseJson, 'lastUpdaterId'),
                                self.GetJSONTagValue(testCaseJson, 'isComplex'),
                                self.GetJSONTagValue(testCaseJson, 'testcaseSequence'),
                                self.GetJSONTagValue(testCaseJson, 'projectName'),
                                self.GetJSONTagValue(testCaseJson, 'testcaseId'),
                                self.GetJSONTagValue(testCaseJson, 'customProcessedProperties'),
                                self.GetJSONTagValue(testCaseJson, 'versionNumber'),
                                self.GetJSONTagValue(testCaseJson, 'automated'),
                                self.GetJSONTagValue(testCaseJson, 'creationDate'),
                                self.GetJSONTagValue(testCaseJson, 'name'),
                                customFieldValueListObj,
                                self.GetJSONTagValue(testCaseJson, 'creatorId'),
                                self.GetJSONTagValue(testCaseJson, 'testcaseShared'),
                                self.GetJSONTagValue(testCaseJson, 'versionCreatedBy'))

        tcrTreeTestCaseObj = CTcrTreeTestCase(self.GetJSONTagValue(jsonContent, 'lastModifiedOn'),
                                              self.GetJSONTagValue(jsonContent, 'releaseName'),
                                              self.GetJSONTagValue(jsonContent, 'stateFlag'),
                                              self.GetJSONTagValue(jsonContent, 'projectIdParam'),
                                              self.GetJSONTagValue(jsonContent, 'tcrCatalogTreeId'),
                                              self.GetJSONTagValue(jsonContent, 'projectId'),
                                              self.GetJSONTagValue(jsonContent, 'orderId'),
                                              self.GetJSONTagValue(jsonContent, 'original'),
                                              testCaseObj,
                                              self.GetJSONTagValue(jsonContent, 'releaseId'),
                                              self.GetJSONTagValue(jsonContent, 'versionNumber'),
                                              self.GetJSONTagValue(jsonContent, 'isDerivedFromBDD'),
                                              self.GetJSONTagValue(jsonContent, 'maxVersionNumber'),
                                              self.GetJSONTagValue(jsonContent, 'id'),
                                              self.GetJSONTagValue(jsonContent, 'revision'))
        return tcrTreeTestCaseObj

    def GetAutomationExecutionMetricsByCriteria(self, releaseId, CycletcrCatalogTreeId, cyclePhaseId, phaseStartDate, phaseEndDate):

        executionList = []
        passedCount   = 0
        failedCount   = 0
        BlockedCount  = 0
        wipCount = 0
        newDefectCount  = 0
        existingDefectCount = 0
        newdefectList = []
        existingdefectList = []

        testCaseCount   =  self.getTestCaseCountByCycleTcrCatalogTreeId(CycletcrCatalogTreeId, releaseId)


        self.GetAllExecutionsContextByCriteria(cyclePhaseId, releaseId, testCaseCount, executionList)

        for executionItem in executionList:
            newdefectTempList       = []
            existingdefectTempList  = []
            if executionItem.lastTestResultObj is not None:
                if executionItem.lastTestResultObj.executionStatus == "1":
                    passedCount = passedCount + 1
                elif executionItem.lastTestResultObj.executionStatus   == "2":
                    failedCount = failedCount + 1
                elif executionItem.lastTestResultObj.executionStatus == "3":
                    wipCount = wipCount + 1
                elif executionItem.lastTestResultObj.executionStatus   == "4":
                    BlockedCount = BlockedCount + 1
            if len(executionItem.defectList) > 0:
                for item in executionItem.defectList:

                    #convert defect created date format to MM/DD/YYYY
                    if item.createdDate is None:
                        newdefectTempList.append(item)
                    else:
                        createdDate = datetime.datetime.strptime(item.createdDate, "%Y-%m-%d").strftime("%m/%d/%Y")

                        if ( (createdDate >= phaseStartDate) and (createdDate <= phaseEndDate)):
                            newdefectTempList.append(item)
                        else:
                            existingdefectTempList.append(item)
                self.ConvertToUniqueList(newdefectTempList, newdefectList)
                self.ConvertToUniqueList(existingdefectTempList, existingdefectList)

        newDefectCount = len(newdefectList)
        existingDefectCount = len(existingdefectList)

        metricObj   = CZephyrCyclePhaseMetric(passedCount, failedCount, BlockedCount, wipCount, newDefectCount, existingDefectCount, testCaseCount)
        return metricObj

    def ConvertToUniqueList(self, DataList, outputList):

        for dataListItem in DataList:
            isDataItemPresent = False
            for dataOutputList in outputList:
                if dataListItem.bugId == dataOutputList.bugId:
                    isDataItemPresent = True
                    break
            if isDataItemPresent is False:
                outputList.append(dataListItem)


class CZephyrMetricsThread(threading.Thread):

    def __init__(self, pThreadId, pThreadName, pZephyrProjectName):

        threading.Thread.__init__(self)
        self.mThreadId          =   pThreadId
        self.mThreadName        =   pThreadName
        self.mZephyrProjectName =   pZephyrProjectName

    def run(self):

        sendLogToStdout("CZephyrMetricsThread::run Starting %s" %(self.mThreadName))

        cfg = CfgReader(ZEPHYR_CONFIG_PATH)

        # Initializing Zephyr instance
        sendLogToStdout(datetime.datetime.now())
        zephyrObj = CZephyr(cfg, self.mZephyrProjectName)

        # Update the context in zephyrObj object
        zephyrObj.updateProjectContext(self.mZephyrProjectName)

        # zephyrObj.createTestRepoJson(dictData)
        zephyrObj.generateZephyrMetrics()

        zephyrObj.closeZephyrSession()

        sendLogToStdout("CZephyrMetricsThread::run Exiting %s" %(self.mThreadName))

def test_clone_phase_process():

    cfg = CfgReader('config.txt')
    add_zephyr_log_handler("./")

    #Input variables
    releaseName = "Automation_Testing_Release"
    ProjectName = "NCI Roku"
    AutomationTemplateCycleName = "PROXY_Sample_Automation_Test_Cycle"
    AutomationTemplatePhaseName = "PROXY_Sample_Automation_Phase_Test_Template_1"
    environment = "Production"
    buildInfo = "Roku 5.11"
    cyclePhaseList = []

    #New Cycle Name
    currentTime = datetime.datetime.now().strftime("%d%b%y_%H%M%S")
    newCycleName = AutomationTemplateCycleName + "_" + str(currentTime)

    #New cycle Phase name
    newCyclePhaseName = "TEST_" + AutomationTemplatePhaseName + "_" + str(currentTime)

    #Initializing Zephyr instance
    zephyrObj = CZephyr(cfg, ProjectName, releaseName, AutomationTemplateCycleName, AutomationTemplatePhaseName)

    # Get cycle Detail of existing cycle
    UpdateCycleDetailContextStatus = zephyrObj.UpdateAutomationCycleDetailContext()

    #Get cycle phase detail of existing cycle phase
    cycleId, cyclePhaseID = zephyrObj.getCycleInfo(AutomationTemplatePhaseName, AutomationTemplateCycleName)

    #Clone cycle using existing automation cycle
    #newCyclePhaseId = zephyrObj.cloneCycle(ProjectName, AutomationTemplatePhaseName, newCycleName, True, True)
    newCyclePhaseId, newTcrCatalogTreeId  = zephyrObj.clonePhase(cycleId, cyclePhaseID)

    #Assign testcases scheduled in cyclePhase to current logged in user
    assignCyclePhaseTestCasesStatus = zephyrObj.assignCyclePhaseTestCases(newCyclePhaseId, newTcrCatalogTreeId)

    #Rename cycle phase name
    updateCyclePhaseValuesWithCurrentDateStatus = zephyrObj.updateCyclePhaseValuesWithCurrentDate(cycleId, newCyclePhaseName, newCyclePhaseId)

    #Get releaseId by release name
    releaseId  = zephyrObj.getReleaseId(releaseName)

    #Get Test case count by CycleTcrCatalogTreeID
    testCaseCount = zephyrObj.getTestCaseCountByCycleTcrCatalogTreeId(newTcrCatalogTreeId, releaseId)

    #Get execution scheduled in newCycleId and releaseId
    executionDetailList = []
    GetAllExecutionsContextforCurrentUserByCriteriaStatus =  zephyrObj.GetAllExecutionsContextforCurrentUserByCriteria(newCyclePhaseId, releaseId, testCaseCount, executionDetailList)

    #Update test case status
    zephyrObj.test_update_execution_status(newCyclePhaseId, executionDetailList)

    # Update execution result in new automation cycle by zephyr ticket ID
    # updateExecutionResultByZephyrID_11776_Status = zephyrObj.updateExecutionResultByZephyrID(11776, 1, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11691_Status = zephyrObj.updateExecutionResultByZephyrID(11691, 2, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11692_Status = zephyrObj.updateExecutionResultByZephyrID(11692, 3, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11693_Status = zephyrObj.updateExecutionResultByZephyrID(11693, 4, 100, excutionDetailList)

    # Update execution result in new automation cycle by externalID (JIRA ID)
    #zephyrObj.updateExecutionResultByExternalID("", 1, 100)
    #zephyrObj.updateExecutionResultByExternalID("AP-9090", 2, 100, executionDetailList)
    # updateExecutionResultByExternalID_AP-8905_Status = zephyrObj.updateExecutionResultByExternalID("AP-8905", 3, 100)
    # updateExecutionResultByExternalID_AP-8903_Status = zephyrObj.updateExecutionResultByExternalID("AP-8903", 4, 100)

def test_clone_cycle_process(cfg):

    # Input variables
    releaseName = "AP Native CI"
    ProjectName = "SlingTV Master"
    AutomationTemplateCycleName = "AP_Automation_Test_Results"
    AutomationTemplatePhaseName = "AP_Automation_Cycle_Test_Template"

    # New Cycle Name
    currentTime = datetime.datetime.now().strftime("%d%b%y_%H%M%S")
    newCycleName = AutomationTemplateCycleName + "_" + str(currentTime)

    # Initializing Zephyr instance
    zephyrObj = CZephyr(cfg, ProjectName, releaseName, AutomationTemplateCycleName, AutomationTemplatePhaseName)

    # Get cycle Detail of existing cycle
    UpdateCycleDetailContextStatus = zephyrObj.UpdateAutomationCycleDetailContext()

    # Get cycle phase detail of existing cycle phase
    cycleId, cyclePhaseId = zephyrObj.getCycleInfo(AutomationTemplatePhaseName, AutomationTemplateCycleName)

    # Clone cycle using existing automation cycle
    newCyclePhaseId, newTcrCatalogtreeId = zephyrObj.cloneCycle(newCycleName, True, True)

    # Assign testcases scheduled in cyclePhase to current logged in user
    assignCyclePhaseTestCasesStatus = zephyrObj.assignCyclePhaseTestCases(newCyclePhaseId, newTcrCatalogtreeId)

    # Get releaseId by release name
    releaseId = zephyrObj.getReleaseId(releaseName)

    # Get Test case count by CycleTcrCatalogTreeID
    testCaseCount = zephyrObj.getTestCaseCountByCycleTcrCatalogTreeId(newTcrCatalogtreeId, releaseId)

    # Get execution scheduled in newCycleId and releaseId
    executionDetailList = []

    GetAllExecutionsContextforCurrentUserByCriteriaStatus = zephyrObj.GetAllExecutionsContextforCurrentUserByCriteria(newCyclePhaseId, releaseId, testCaseCount, executionDetailList)

    # Update test case status
    zephyrObj.test_update_execution_status(newCyclePhaseId, executionDetailList)

    # Update execution result in new automation cycle by zephyr ticket ID
    # updateExecutionResultByZephyrID_11776_Status = zephyrObj.updateExecutionResultByZephyrID(11776, 1, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11691_Status = zephyrObj.updateExecutionResultByZephyrID(11691, 2, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11692_Status = zephyrObj.updateExecutionResultByZephyrID(11692, 3, 100, excutionDetailList)
    # updateExecutionResultByZephyrID_11693_Status = zephyrObj.updateExecutionResultByZephyrID(11693, 4, 100, excutionDetailList)

    # Update execution result in new automation cycle by externalID (JIRA ID)
    # updateExecutionResultByExternalID_AP-9094_Status = zephyrObj.updateExecutionResultByExternalID("AP-9094", 1, 100, excutionDetailList)
    # updateExecutionResultByExternalID_AP-9067_Status = zephyrObj.updateExecutionResultByExternalID("AP-9067", 2, 100, excutionDetailList)
    # updateExecutionResultByExternalID_AP-8905_Status = zephyrObj.updateExecutionResultByExternalID("AP-8905", 3, 100, excutionDetailList)
    # updateExecutionResultByExternalID_AP-8903_Status = zephyrObj.updateExecutionResultByExternalID("AP-8903", 4, 100, excutionDetailList)


def test_createCycleAndPhase_process():

    cfg                         = CfgReader('config.txt')
    add_zephyr_log_handler("./")

    #Input variables
    releaseName = "Automation_Testing_Release"
    ProjectName = "NCI Android"
    AutomationTemplateCycleName = "Sample_Automation_Test_Cycle"
    AutomationTemplatePhaseName = "Sample_Automation_Phase_Test_Template"
    environment                 = "Production"
    buildInfo                   = "Sample Build Info"
    cyclePhaseList              = []
    zephyrCycleInfo             = None

    #New Cycle Name
    currentTime                 = datetime.datetime.now().strftime("%d%b%y")
    newCycleName                = AutomationTemplateCycleName + "_" + str(currentTime)

    #New cycle Phase name
    newCyclePhaseName           = "TEST_" + AutomationTemplatePhaseName + "_" + str(currentTime)

    #Initializing Zephyr instance
    zephyrObj                   = CZephyr(cfg, ProjectName, releaseName, AutomationTemplateCycleName, AutomationTemplatePhaseName)

    #Get releaseId by release name
    releaseId                   = zephyrObj.getReleaseId(releaseName)

    #Get ProjectId by project name
    projectId                   = zephyrObj.getProjectID(ProjectName)

    testCaseTreeIdList = []


    #suiteType = "NON_NCI"
    #suiteType = "CLIENT_INTEGRATION_SMOKE"
    suiteType = "SYSTEM_SMOKE"

    if (suiteType in ZEPHYR_TEST_REPO_PATH.keys()):
        AutomationSmokefolderHierarchiy = ZEPHYR_TEST_REPO_PATH[suiteType]
        status = zephyrObj.getTestCaseListByZephyrTestFolder(releaseId, AutomationSmokefolderHierarchiy,
                                                             testCaseTreeIdList, "automated")
        if (status is False):
            sendLogToStdout("Incorrect Folder path : %s" % AutomationSmokefolderHierarchiy)
            sys.exit(-1)
    else:
        testCaseTreeIdList = zephyrObj.getAutomatedTestCasesByZQLQuery(releaseId, projectId)
        #sendLogToStdout("testCaseList=" + str(testCaseTreeIdList))


    zephyrCycleInfo             = zephyrObj.getCycleInfoByName(releaseId, newCycleName)

    if zephyrCycleInfo is None:
        zephyrCycleInfo         = zephyrObj.createZephyrCycle(newCycleName, releaseId, environment, buildInfo, cyclePhaseList,
                                                      False)

    phaseListDict               = zephyrObj.getCyclePhasList(releaseId, zephyrCycleInfo.id,AutomationTemplatePhaseName)

    if len(phaseListDict) > 0:
        PhaseNameList           = (phaseListDict.keys())
        PhaseNameList.sort()
        maxIternumber           = int(str(PhaseNameList[-1]).split("_")[-1])
        newCyclePhaseName       = AutomationTemplatePhaseName + "_" + str(maxIternumber + 1)
    else:
        newCyclePhaseName       = AutomationTemplatePhaseName + "_" + str(len(phaseListDict) +  1)

    zephyrPhaseInfo             = zephyrObj.createPhase(zephyrCycleInfo, newCyclePhaseName)

    if (suiteType in ZEPHYR_TEST_REPO_PATH.keys()):
        zephyrObj.createPhaseTestPlanbyTreeId(zephyrPhaseInfo.id, testCaseTreeIdList)
    else:
        zephyrObj.createPhaseTestPlanbyTestCaseIds(zephyrPhaseInfo.id, testCaseTreeIdList)

    testCaseIdToInfoDict        = zephyrObj.performAllCyclePhaseTreeIdAssignement(zephyrPhaseInfo.id)

    executionListObj            = []

    zephyrObj.GetAllExecutionsContextForAllPhaseTCRID(zephyrPhaseInfo.id, releaseId, testCaseIdToInfoDict, executionListObj)

    zephyrObj.test_update_execution_status(zephyrPhaseInfo.id, executionListObj)

    #zephyrObj.updateExecutionTestCaseStepByExternalID("AP-6339", 1, 2, zephyrPhaseInfo.id, executionListObj)
    #zephyrObj.updateExecutionTestCaseStepByExternalID("AP-6339", 2, 1, zephyrPhaseInfo.id, executionListObj)

    #zephyrObj.updateExecutionTestCaseStepByZephyrID(42362, 1, 2, zephyrPhaseInfo.id,
                                                    #executionListObj)
    #zephyrObj.updateExecutionTestCaseStepByZephyrID(42362, 2 , 1, zephyrPhaseInfo.id,
                                                    #executionListObj)

    zephyrObj.closeZephyrSession()

def getTestRepositoryInfo(sys):

    sendLogToStdout(datetime.datetime.now())
    projectNameList = ["NCI Longevity", "NCI Android", "NCI iOS", "NCI tvOS"]#, "NCI Adaptive Player", "NCI Roku"]
    zephyrThreadlist = []

    for projectName in projectNameList:
        zephyrThread = CZephyrMetricsThread("1", projectName, projectName)
        zephyrThread.start()
        zephyrThreadlist.append(zephyrThread)

    for zephyrThread in zephyrThreadlist:
        zephyrThread.join()

    sendLogToStdout(datetime.datetime.now())

def test_cycle_fetch():

    cfg                         = CfgReader('config.txt')
    add_zephyr_log_handler("./")

    #Input variables
    releaseName = "Automation_Testing_Release"
    ProjectName = "NCI Roku"
    AutomationTemplateCycleName = "PROXY_Sample_Automation_Test_Cycle"
    AutomationTemplatePhaseName = "PROXY_Sample_Automation_Phase_Test_Template"
    environment = "Production"
    buildInfo = "Roku 5.11"
    cyclePhaseList              = []

    #New Cycle Name
    currentTime                 = datetime.datetime.now().strftime("%d%b%y_%H%M%S")
    newCycleName                = AutomationTemplateCycleName

    #New cycle Phase name
    newCyclePhaseName           = "TEST_" + AutomationTemplatePhaseName + "_" + str(currentTime)

    #Initializing Zephyr instance
    zephyrObj                   = CZephyr(cfg, ProjectName, releaseName, AutomationTemplateCycleName, AutomationTemplatePhaseName)

    #Get releaseId by release name
    releaseId                   = zephyrObj.getReleaseId(releaseName)

    #Get ProjectId by project name
    projectId                   = zephyrObj.getProjectID(ProjectName)

    cycleInfo                   = zephyrObj.getCycleInfoByName(releaseId, "PROXY_Sample_Automation_Test_Cycle")

    cyclePhaseInfo              = zephyrObj.getCyclePhaseByName( releaseId, cycleInfo.id, "PROXY_Sample_Automation_Phase_Test_Template_1")

def main():

    try:

        #getTestRepositoryInfo(sys)

        test_createCycleAndPhase_process()

        #test_cycle_fetch()

        #test_clone_phase_process()

        sys.exit(0)

    except Exception as e:
        print ("Exception in main")
        raise

if __name__ == "__main__":
    main()
