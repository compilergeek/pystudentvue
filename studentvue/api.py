import requests
import xmltodict, json
from xml.sax import saxutils as su

def create(district_url, username, password):
    return _StudentVueApi(district_url, username, password)


class _StudentVueApi():

    def __init__(self, district_url, username, password, endpoint="/Service/PXPCommunication.asmx/ProcessWebServiceRequest"):
        assert endpoint.startswith("/")
        assert not endpoint.endswith("/")

        self.district_url = district_url
        self.username = username
        self.password = password
        self.endpoint = endpoint

    def gradebook_overview(self):
        data = {}
        data["userID"] = self.username
        data["password"] = self.password
        data["skipLoginLog"] = "true"
        data["parent"] = "false"
        data["webServiceHandleName"] = "PXPWebServices"
        data["methodName"] = "Gradebook"
        data["paramStr"] = "<Parms><ChildIntID>0</ChildIntID></Parms>"

        headers = {}
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        r = requests.request(method="POST", url=self.district_url + self.endpoint, data=data, headers=headers)
        unescaped = su.unescape(r.text)
        converted = xmltodict.parse(unescaped)
        gradebook = json.loads(json.dumps(converted))['string']["Gradebook"]

        periods = []
        currentPeriod = None
        for period in gradebook["ReportingPeriods"]["ReportPeriod"]:
            obj = _ReportingPeriod(period["@Index"], period["@StartDate"], period["@EndDate"], period["@GradePeriod"])
            periods.append(obj)

            if gradebook["ReportingPeriod"]["@GradePeriod"] == period["@GradePeriod"]:
                currentPeriod = obj

        courses = []
        for course in gradebook["Courses"]["Course"]:
            courses.append(_CourseInfo(course["@Title"], course["@Period"], course["@StaffEMail"], course["@Room"], course["@Staff"]))

        return periods, currentPeriod, courses


class _ReportingPeriod():

    def __init__(self, index, start_date, end_date, name):
        self.index = index
        self.start_date = start_date
        self.end_date = end_date
        self.name = name

class _CourseInfo():

    def __init__(self, name, period, email, room, staff):
        self.name = name
        self.period = period
        self.email = email
        self.room = room
        self.staff = staff