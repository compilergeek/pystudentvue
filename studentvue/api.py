"""
    Copyright (C) 2019 Yoland Gao

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import requests
import xmltodict, json
from xml.sax import saxutils as su

from decimal import Decimal


def create(district_url, username, password, check_login_credentials=True):
    return _StudentVueApi(district_url, username, password, check_login_credentials=check_login_credentials)


class StudentVueHelper(object):

    @staticmethod
    def find_assignment_by_id(courses, assignment_id):
        for course in courses:
            assignments = course.assignments
            for assignment in assignments:
                if assignment.id == assignment_id:
                    return assignment
        return None


class _StudentVueApi:

    def __init__(self, district_url, username, password,
                 endpoint="/Service/PXPCommunication.asmx/ProcessWebServiceRequest", check_login_credentials=True):
        assert endpoint.startswith("/")
        assert not endpoint.endswith("/")

        self.district_url = district_url
        self.username = username
        self.password = password
        self.endpoint = endpoint

        if check_login_credentials and self._gradebook() is None:
            raise AssertionError("Login error")

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
        if "System.NullReferenceException" in unescaped:
            return None
        converted = xmltodict.parse(unescaped)

        converted_json = json.loads(json.dumps(converted))['string']
        if "RT_ERROR" in converted_json:
            return None

        gradebook = json.loads(json.dumps(converted))['string']["Gradebook"]
        return gradebook

    def _gradebook_overview(self, gradebook):
        if gradebook == None:
            return None, None
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
        if gradebook is None:
            raise AssertionError()
        periods, current_period = self._gradebook_overview(gradebook)

        courses = []
        for course in gradebook["Courses"]["Course"]:
            assignments = []
            marks_root = None
            assignments_root = None

            if course is not None and "Marks" in course and course["Marks"] is not None and "Mark" in course["Marks"]:
                if type(course["Marks"]["Mark"]) == list:
                    marks_root = course["Marks"]["Mark"][0]
                    assignments_root = marks_root["Assignments"]
                else:
                    marks_root = course["Marks"]["Mark"]
                    assignments_root = course["Marks"]["Mark"]["Assignments"]

            if assignments_root is not None:
                for assignment in assignments_root["Assignment"]:
                    should_exit = False
                    if type(assignments_root["Assignment"]) is dict:
                        assignment = assignments_root["Assignment"]
                        should_exit = True

                    assignments.append(_Assignment(
                        title=assignment["@Measure"],
                        score_type=assignment["@ScoreType"],
                        score=assignment["@Score"],
                        description=assignment["@MeasureDescription"],
                        start_date=assignment["@DropStartDate"],
                        end_date=assignment["@DropEndDate"],
                        due_date=assignment["@DueDate"],
                        date=assignment["@Date"],
                        assignment_type=assignment["@Type"],
                        id=assignment["@GradebookID"],
                        for_grading=(not (assignment["@Notes"] == "(Not For Grading)"))
                    ))

                    if should_exit:
                        break

            if marks_root is None:
                score_raw = 0
                score_string = "N/A"
            else:
                score_raw = marks_root["@CalculatedScoreRaw"]
                score_string = marks_root["@CalculatedScoreString"]


            courses.append(_CourseInfo(course["@Title"], course["@Period"], course["@StaffEMail"], course["@Room"],
                                       course["@Staff"], assignments, score_raw,
                                       score_string))
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

    def __init__(self, title, score_type, score, description, start_date, end_date, due_date, date, assignment_type, id, for_grading):
        self.title = title
        self.id = id
        self.score_type = score_type

        if "out of" in score:
            #Raw score
            score_process = score.split(" out of ")

            self.raw_score_earned = Decimal(score_process[0].strip())
            self.raw_score_possible = Decimal(score_process[1].strip())

            if self.raw_score_possible <= 0:
                self.score = 100
            else:
                self.score = (self.raw_score_earned / self.raw_score_possible) * Decimal(100)
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
        self.for_grading = for_grading
