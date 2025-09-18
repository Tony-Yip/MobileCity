"""
Global functions.
"""
import csv
from datetime import datetime, timedelta
import json
import math
import os
from os import listdir
import shelve

import pandas as pd

def read_df_persona_data(row):
    persona_data = dict()

    persona_data['name'] = str(row['agent_id'])
    persona_data['name_initials'] = str(row['agent_id'])
    persona_data['monitor_id'] = int(row['monitor_id'])

    persona_data['gender'] = str(row['sex'])
    persona_data['age'] = int(row['age'])
    persona_data['employment_status'] = str(row['job_category'])
    persona_data['educational_background'] = str(row['academic_history'])
    persona_data['income_level'] = str(row['house_income'])

    persona_data['hobbies'] = str(row['summary'])
    persona_data['characters'] = str(row['traits'])

    persona_data['living_area'] = str(row['living_place'])
    persona_data['working_place'] = str(row['working_place'])
    persona_data['x'] = int(row['x'])
    persona_data['y'] = int(row['y'])

    sleeping_time = str(row['sleeping_time']).split('-')
    sleeping_time_pm = sleeping_time[0].strip()
    sleeping_time_am = sleeping_time[1].strip()

    sleep_pm = {
        "Action": "sleeping",
        "Place": row['living_place'],
        "start_time": sleeping_time_pm,
        "end_time": "23:59:59",
        "Fullness": 0,
        "Happiness": 0,
        "Health": 0,
        "Energy": 0,
        "Emoji": "\ud83d\ude34"
    }

    sleep_am = {
        "Action": "sleeping",
        "Place": row['living_place'],
        "start_time": "00:00:00",
        "end_time": sleeping_time_am,
        "Fullness": -1,
        "Happiness": 1,
        "Health": 1,
        "Energy": 2,
        "Emoji": "\ud83d\ude34"
    }


    persona_data['weekend'] = [
        sleep_am, sleep_pm
    ]

    if not pd.isna(row['working_time']):
        working_time = str(row['working_time']).split('-')
        working_time_am = working_time[0].strip()
        working_time_pm = working_time[1].strip()
        working_hours = int(working_time_pm[:2])-int(working_time_am[:2])

        if working_hours<7:
            work_apm = {
                "Action": "work in the company",
                "Place": str(row['working_place']),
                "start_time": working_time_am,
                "end_time": working_time_pm,
                "Fullness": 0,
                "Happiness": 0,
                "Health": 0,
                "Energy": 0,
                "Emoji": "\ud83d\udcbc"
            }
            persona_data['weekdays'] = [
                sleep_am, work_apm, sleep_pm
            ]
        else:
            work_am = {
                "Action": "work in the company",
                "Place": str(row['working_place']),
                "start_time": working_time_am,
                "end_time": "12:00:00",
                "Fullness": 0,
                "Happiness": 0,
                "Health": 0,
                "Energy": 0,
                "Emoji": "\ud83d\udcbc"
            }
            work_pm = {
                "Action": "work in the company",
                "Place": str(row['working_place']),
                "start_time": "13:00:00",
                "end_time": working_time_pm,
                "Fullness": 0,
                "Happiness": 0,
                "Health": 0,
                "Energy": 0,
                "Emoji": "\ud83d\udcbc"
            }    
            persona_data['weekdays'] = [
                sleep_am, work_am, work_pm, sleep_pm
            ]

    else:
        persona_data['weekdays'] = [
            sleep_am, sleep_pm
        ]        

    persona_data['human_parameters'] = [float(row['HP_0']),float(row['HP_1']),float(row['HP_2']),float(row['HP_3']),float(row['HP_4']),float(row['HP_5']),float(row['HP_6']),float(row['HP_7']),float(row['HP_8']),float(row['HP_9']),float(row['HP_10']),float(row['HP_11']),float(row['HP_12']),float(row['HP_13']),float(row['HP_14']),float(row['HP_15'])]
    # persona_data['cat'] = int(row['cat'])
    persona_data['cat'] = 300
    return persona_data

def split_string(input_string, A, B):
    start_index_A = input_string.find(A)
    start_index_B = input_string.find(B, start_index_A + len(A))
    
    if start_index_A == -1 or start_index_B == -1:
        return False, False

    middle = input_string[start_index_A + len(A):start_index_B]

    after_B = input_string[start_index_B + len(B):]

    return middle, after_B

def determine_public_intervals(calendar_0, calendar_1, earlies_start_time_place, latest_end_tim_place, earlies_start_time_task, latest_end_time_task):

  def merge_intervals(A, B):
    intervals = sorted(A + B, key=lambda x: x[0])
    merged = []
    for interval in intervals:
        if not merged or merged[-1][1] < interval[0]:
            merged.append(interval)
        else:
            merged[-1][1] = max(merged[-1][1], interval[1])
    return merged
  
  earlies_start_time = max(datetime.strptime(earlies_start_time_place, '%H:%M'), datetime.strptime(earlies_start_time_task, '%H:%M'))
  latest_end_time = min(datetime.strptime(latest_end_tim_place, '%H:%M'), datetime.strptime(latest_end_time_task, '%H:%M'))

  for i in range(1,7):
    stack_0 = [[x_i['start_time'], x_i['end_time']] for x_i in calendar_0[i]][::-1]
    stack_1 = [[x_i['start_time'], x_i['end_time']] for x_i in calendar_1[i]][::-1]

    stack_0 = [[datetime.strptime(a_i[0], '%H:%M:%S'), datetime.strptime(a_i[1], '%H:%M:%S')] for a_i in stack_0]
    stack_1 = [[datetime.strptime(b_i[0], '%H:%M:%S'), datetime.strptime(b_i[1], '%H:%M:%S')] for b_i in stack_1]

    new_stack = merge_intervals(stack_0, stack_1)

    start_time = earlies_start_time
    
    is_valid = False
    for interval in new_stack:
      end_time = start_time+timedelta(hours=3)
      if end_time > latest_end_time:
        break
      if end_time <= interval[0]:
        is_valid = True
        for j_0 in range(len(stack_0)):
          if start_time<stack_0[j_0][0]: break
        for j_1 in range(len(stack_1)):
          if start_time<stack_1[j_1][0]: break
        break
      else:
        start_time = interval[1]
  
    if is_valid:
      return start_time, i, len(stack_0)-j_0, len(stack_1)-j_1

  return -1, -1, -1, -1

def requirement_filter(basic_requirements):
  for key, value in basic_requirements.items():
    if value<0: value=0
    if value>10: value=10
    basic_requirements[key] = round(value, 2)
  return basic_requirements

def transfer_tile_info(tile_info):
  if tile_info['arena'] != -1:
    character_place = tile_info['sector']+':'+tile_info['arena']
  elif tile_info['location'] != -1:
    character_place = tile_info['sector']+':'+tile_info['location']
  else:
    character_place = tile_info['sector']
  return character_place

def get_cache(key):
    cache_path = 'fake_cache'
    with shelve.open(cache_path) as shelf:
      value = shelf.get(key)
    return value

def write_cache(key, value):
    cache_path = 'fake_cache'
    with shelve.open(cache_path) as shelf:
      shelf[key] = value

def find_json_in_subfolders(folder, x):
    for root, dirs, files in os.walk(folder):
        target_file = f"{x}.json"
        if target_file in files:
            file_path = os.path.join(root, target_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
    return ValueError(f'{x} does not exist!')

def read_file_to_list(curr_file, header=False, strip_trail=True): 
  if not header: 
    analysis_list = []
    with open(curr_file) as f_analysis_file: 
      data_reader = csv.reader(f_analysis_file, delimiter=",")
      for count, row in enumerate(data_reader): 
        if strip_trail: 
          row = [i.strip() for i in row]
        analysis_list += [row]
    return analysis_list
  else: 
    analysis_list = []
    with open(curr_file) as f_analysis_file: 
      data_reader = csv.reader(f_analysis_file, delimiter=",")
      for count, row in enumerate(data_reader): 
        if strip_trail: 
          row = [i.strip() for i in row]
        analysis_list += [row]
    return analysis_list[0], analysis_list[1:]

def calculate_time_money_cost(graph, paths):
  money_cost = 0
  walking_time_cost = 0
  onboard_time_cost = 0
  i = 0
  while i<len(paths)-1:
    edge_data = graph.get_edge_data(paths[i], paths[i+1])
    if edge_data['edge_type']=='walking':
      walking_time_cost += edge_data['time_cost']
    else:
      onboard_time_cost += edge_data['time_cost']
    money_cost += edge_data['money_cost']
    i += 1
  return walking_time_cost, onboard_time_cost, money_cost

def convert_minutes_to_rounded_seconds(x):
    # Convert minutes to seconds
    seconds = x * 60
    rounded_seconds = math.ceil(seconds / 15) * 15
    return rounded_seconds

if __name__ == '__main__':
  pass
















