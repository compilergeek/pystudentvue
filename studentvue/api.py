import requests
import xmltodict, json
from xml.sax import saxutils as su

from decimal import Decimal


def create(district_url, username, password):
    return _StudentVueApi(district_url, username, password)


class _StudentVueApi:

    def __init__(self, district_url, username, password,
                 endpoint="/Service/PXPCommunication.asmx/ProcessWebServiceRequest"):
        assert endpoint.startswith("/")
        assert not endpoint.endswith("/")

        self.district_url = district_url
        self.username = username
        self.password = password
        self.endpoint = endpoint

    def _gradebook(self, reporting_period_index=None):
        data = {}
        data["userID"] = self.username
        data["password"] = self.password
        data["skipLoginLog"] = "true"
        data["parent"] = "false"
        data["webServiceHandleName"] = "PXPWebServices"
        data["methodName"] = "Gradebook"

        if reporting_period_index:
            data["paramStr"] = "<Parms><ChildIntID>0</ChildIntID><ReportPeriod>" + str(
                reporting_period_index) + "</ReportPeriod></Parms>"
        else:
            data["paramStr"] = "<Parms><ChildIntID>0</ChildIntID></Parms>"

        headers = {}
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        r = requests.request(method="POST", url=self.district_url + self.endpoint, data=data, headers=headers)
        unescaped = su.unescape(r.text)
        converted = xmltodict.parse(unescaped)
        gradebook = json.loads(json.dumps(converted))['string']["Gradebook"]

        return gradebook

    def _gradebook_overview(self, gradebook):
        periods = []
        current_period = None
        for period in gradebook["ReportingPeriods"]["ReportPeriod"]:
            obj = _ReportingPeriod(period["@Index"], period["@StartDate"], period["@EndDate"], period["@GradePeriod"])
            periods.append(obj)

            if gradebook["ReportingPeriod"]["@GradePeriod"] == period["@GradePeriod"]:
                current_period = obj
        return periods, current_period

    def gradebook_overview(self):
        return self._gradebook_overview(gradebook=self._gradebook(None))

    def gradebook_detailed(self, reporting_period):
        gradebook = self._gradebook(reporting_period.index)
        periods, current_period = self._gradebook_overview(gradebook)

        courses = []
        for course in gradebook["Courses"]["Course"]:
            assignments = []
            for assignment in course["Marks"]["Mark"]["Assignments"]["Assignment"]:
                assignments.append(_Assignment(
                    title=assignment["@Measure"],
                    score_type=assignment["@ScoreType"],
                    score=assignment["@Score"],
                    description=assignment["@MeasureDescription"],
                    start_date=assignment["@DropStartDate"],
                    end_date=assignment["@DropEndDate"],
                    due_date=assignment["@DueDate"],
                    date=assignment["@Date"],
                    assignment_type=assignment["@Type"]
                ))
            courses.append(_CourseInfo(course["@Title"], course["@Period"], course["@StaffEMail"], course["@Room"],
                                       course["@Staff"], assignments, course["Marks"]["Mark"]["@CalculatedScoreRaw"],
                                       course["Marks"]["Mark"]["@CalculatedScoreString"]))
        return periods, current_period, courses


class _ReportingPeriod:

    def __init__(self, index, start_date, end_date, name):
        self.index = index
        self.start_date = start_date
        self.end_date = end_date
        self.name = name


class _CourseInfo:

    def __init__(self, name, period, email, room, staff, assignments, overall_grade, overall_grade_letter):
        self.name = name
        self.period = period
        self.email = email
        self.room = room
        self.staff = staff
        self.assignments = assignments
        self.overall_grade = overall_grade
        self.overall_grade_letter = overall_grade_letter


class _Assignment:

    def __init__(self, title, score_type, score, description, start_date, end_date, due_date, date, assignment_type):
        self.title = title
        self.score_type = score_type

        if "out of" in score:
            #Raw score
            score_process = score.split(" out of ")

            self.rawScoreEarned = Decimal(score_process[0].strip())
            self.rawScorePossible = Decimal(score_process[1].strip())
            self.score = (self.rawScoreEarned / self.rawScorePossible) * Decimal(100)
        elif "()" in score:
            score = score.replace("()", "")
            self.score = Decimal(score.strip())
        else:
            self.score = None
            self.score_type = None

        self.description = description
        self.start_date = start_date
        self.end_date = end_date
        self.due_date = due_date
        self.date = date
        self.assignment_type = assignment_type
