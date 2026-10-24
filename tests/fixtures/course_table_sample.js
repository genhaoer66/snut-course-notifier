// Synthetic response only; no school or student data.
var unitCount = 12;

var teachers = [{id:1,name:"教师甲",lab:false},{id:2,name:"教师乙",lab:false}];
var activity = new TaskActivity(
    actTeacherId.join(','), actTeacherName.join(','),
    "SAMPLE_A(SECTION_A)",
    "示例课程A"+periodInfo+"(SECTION_A)",
    "0", "101", "0110000000000000000000",
    null, null, assistantName, "", "");
index = 2*unitCount+4;
table0.activities[index][table0.activities[index].length] = activity;
index = 2*unitCount+5;
table0.activities[index][table0.activities[index].length] = activity;

var teachers = [];
var activity = new TaskActivity(
    actTeacherId.join(','), actTeacherName.join(','),
    "SAMPLE_B(SECTION_B)",
    "示例课程B"+periodInfo+"(SECTION_B)",
    "0", "", "0001000000000000000000",
    null, null, assistantName, "", "");
index = 0*unitCount+2;
table0.activities[index][table0.activities[index].length] = activity;
