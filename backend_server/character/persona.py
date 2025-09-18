import bisect
from datetime import datetime, timedelta
import networkx as nx
import random
import re

from global_methods import *
from mobility_methods import *
from prompt_templates.action_generator import ActionGenerator

class Persona:
  def __init__(self, persona_data: dict):
    self.name = persona_data['name']
    self.persona = persona_data
    # print(f"{self.name} is generated!")
    self.human_parameters = self.persona['human_parameters']
    self.basic_requirements = {'Fullness': 6, 'Happiness': 6, 'Health': 6, 'Energy': 6, 'Sociality': 6}
    self.persona_prompt = self.generate_persona_prompt()

    """The information of the current motivation."""
    self.work_status = True # True: performing actions False: commuting

    self.task_description = 'sleeping'
    self.task_end_time = None
    self.tile = [self.persona['x'], self.persona['y']]

  def generate_persona_prompt(self):
    persona = self.persona

    prompt_file = 'prompt_templates/v3/0_personal_information.txt'
    with open(prompt_file, 'r') as f:
        prompt_content = f.read()

    replacements = {
        '0': persona['name'],
        '1': persona['gender'],
        '2': str(persona['age']),
        '3': persona['employment_status'],
        '4': persona['educational_background'],
        '5': persona['income_level'],
        '6': persona['characters']
    }        
    
    def replace_func(match):
        return replacements.get(match.group(1), match.group(0))
    
    pattern = r'!<INPUT\s+(\d+)>!'
    return re.sub(pattern, replace_func, prompt_content)
  
  def initialize_modules(self, name_list: list[str]):
    self.task_place = self.persona['living_area']
    self.task_emoji = '😴'
    self.task_requirements = {'Fullness': 0, 'Happiness': 0, 'Health': 0, 'Energy': 0}
    self.task_data = None

    self.task_description_ready = None
    self.task_emoji_ready = None
    self.mobility = -1
    self.mobility_number = 0
    self.change_path = True
    self.path = []

    """Agent memory."""
    self.compulsory_task_calendar = []
    self.familiarity = {name: 0 for name in name_list if name!=self.name} # How much you are familiar with some one (0: know nothing 10: know everything)
    self.affinity = {name: 5 for name in name_list if name!=self.name} # How much you like someone (0: no feeling 10: love)
    self.task_memory_past_max = 5
    self.task_memory_past = [] # Things that you have done. Importance decreases by time
    self.task_memory_future = [] # The agreement between you and someone else. A stack.
    self.agents_knowledge = {name: [] for name in name_list if name!=self.name} # The information you know about others.
    self.agents_impression = {name: '' for name in name_list if name!=self.name} # The last conversation.

    """Agent conversation"""
    self.start_conversation = False
    self.in_conversation = False
    self.is_remote_chat = False
    self.conversation_partner = None
    self.conversation_end_time = None
    self.current_chat = None

  def initialize_compulsory_task(self, cur_time):
    if self.compulsory_task_calendar == []: # Initialize the calendar
      for num_days in range(7): 
        future_date = cur_time + timedelta(days=num_days)
        if future_date.weekday() < 5:
          self.compulsory_task_calendar.append(self.persona['weekdays'][::-1])
        else:
          self.compulsory_task_calendar.append(self.persona['weekend'][::-1])
      compulsory_task = self.compulsory_task_calendar[0].pop()
      task_end_time = datetime.strptime(compulsory_task['end_time'], "%H:%M:%S")
      self.task_end_time = cur_time+timedelta(hours=task_end_time.hour, minutes=task_end_time.minute, seconds=task_end_time.second)
    else:
      self.compulsory_task_calendar.pop(0) # Add a new day
      future_date = cur_time + timedelta(days=7)
      if future_date.weekday() < 5:
        self.compulsory_task_calendar.append(self.persona['weekdays'][::-1])
      else:
        self.compulsory_task_calendar.append(self.persona['weekend'][::-1])

  def move_mobility(self, maze):
    x_list, y_list = [], []
    cur_mobility_type = self.mobility['type'][self.mobility_number]

    if self.change_path == True:
      if self.mobility_number+1 >= len(self.mobility['path']):
        sector_arena = self.mobility['path'][self.mobility_number]
        if sector_arena[-2] == ':':
          sector_arena = sector_arena[:-2]
        random_tiles = maze.arena_tiles[sector_arena]
        random_tile_tuple = random.choice(random_tiles)
        x_list.append(random_tile_tuple[1])
        y_list.append(random_tile_tuple[0])
        next_tile_tuple = random_tile_tuple

        """Back to work status"""
        self.work_status = True
        self.task_description = self.task_description_ready
        self.task_emoji = self.task_emoji_ready
        self.mobility_number = 0

        self.tile = [next_tile_tuple[1], next_tile_tuple[0]]
        self.start_conversation = True
        return x_list, y_list
      
      else:
        source_place = self.mobility['path'][self.mobility_number]
        target_place = self.mobility['path'][self.mobility_number+1]          
        if cur_mobility_type == 0:
            source = tuple(maze.location_dict[source_place])
            target = tuple(maze.location_dict[target_place])
            source_place_p, target_place_p = source_place.split(':'), target_place.split(':')
            source_sector, source_arena = source_place_p[0], source_place_p[1]
            target_sector, target_arena = target_place_p[0], target_place_p[1]

            if source_arena == 'Crossing' and target_arena == 'Crossing' and source_sector != target_sector:
              if source[0] < target[0]:
                assert source[0]+3 == target[0] and source[1] == target[1]
                self.path = [[y, source[1]] for y in list(range(target[0]-1, source[0]-1, -1))]
              elif source[0] > target[0]:
                assert source[0]-3 == target[0] and source[1] == target[1]
                self.path = [[y, source[1]] for y in list(range(target[0]+1, source[0]+1))]
              elif source[1] < target[1]:
                assert source[1]+3 == target[1]
                self.path = [[source[0], x] for x in list(range(target[1]-1, source[1]-1, -1))]
              else:
                assert source[1]-3 == target[1]
                self.path = [[source[0], x] for x in list(range(target[1]+1, source[1]+1))]            
                
            else:
              source_sector = source_place.split(':')[0]

              _, path = nx.bidirectional_dijkstra(maze.submap[source_sector]['nx_fake'], source=target, target=source, weight='time_cost')
              self.path = path[:-1]
            next_tile_tuple = self.path.pop()
            x_list, y_list = [next_tile_tuple[1]], [next_tile_tuple[0]]

        else:
          start_station_tile = search_closet_highway(maze, self.tile[0], self.tile[1])
          x_list.append(start_station_tile[0])
          y_list.append(start_station_tile[1])

          source = (start_station_tile[1], start_station_tile[0])
          target_tile_tuple = maze.location_dict[target_place]
          target_station_tile = search_closet_highway(maze, target_tile_tuple[1], target_tile_tuple[0])
          target = (target_station_tile[1], target_station_tile[0])
          
          if cur_mobility_type == 1:
            _, path = nx.bidirectional_dijkstra(maze.PMV_road_graph, source=source, target=target, weight='time_cost')
            self.path = path[::-1]
            for _ in range(2):
              if self.path:
                next_tile_tuple = self.path.pop()
                x_list.append(next_tile_tuple[1])
                y_list.append(next_tile_tuple[0])
          else:
            _, path = nx.bidirectional_dijkstra(maze.bus_road_graph, source=source, target=target, weight='time_cost')
            self.path = path[::-1]
            for _ in range(5):
              if self.path:
                next_tile_tuple = self.path.pop()
                x_list.append(next_tile_tuple[1])
                y_list.append(next_tile_tuple[0])

        self.change_path = False

    else:
      if cur_mobility_type == 0:
        if self.path == []:
          self.mobility_number += 1
          self.change_path = True
          return self.move_mobility(maze)
        next_tile_tuple = self.path.pop()
        x_list, y_list = [next_tile_tuple[1]], [next_tile_tuple[0]]
      elif cur_mobility_type == 1:
        for _ in range(2):
          if self.path:
            next_tile_tuple = self.path.pop()
            x_list.append(next_tile_tuple[1])
            y_list.append(next_tile_tuple[0])
        if self.path == []:
            target_station_tile = search_closet_walkway(maze, next_tile_tuple[1], next_tile_tuple[0])
            x_list.append(target_station_tile[0])
            y_list.append(target_station_tile[1])
            next_tile_tuple = tuple([target_station_tile[1], target_station_tile[0]])
      else:
        for _ in range(5):
          if self.path:
            next_tile_tuple = self.path.pop()
            x_list.append(next_tile_tuple[1])
            y_list.append(next_tile_tuple[0])
        if self.path == []:
            target_station_tile = search_closet_walkway(maze, next_tile_tuple[1], next_tile_tuple[0])
            x_list.append(target_station_tile[0])
            y_list.append(target_station_tile[1])
            next_tile_tuple = tuple([target_station_tile[1], target_station_tile[0]])          

      if self.path == []:
        self.change_path = True
        self.mobility_number += 1

    self.tile = [next_tile_tuple[1], next_tile_tuple[0]]
    if cur_mobility_type == 0:
      self.task_description = 'walking'
      self.task_emoji = '🚶‍♂️'
    elif cur_mobility_type == 1:
      self.task_description = 'on the PMV'
      self.task_emoji = '🛹'
    else:
      self.task_description = 'on the bus'
      self.task_emoji = '🚌'

    return x_list, y_list

  def action_selector(self, cur_time, GPT: ActionGenerator, sunny):
    # relevant_documents = self.memory_module.get_relevant_documents(query=f"It is {cur_time_str} now. What is the next action of {self.name}?")
    compulsory_task_today = self.compulsory_task_calendar[0]
    
    if compulsory_task_today:
      next_compulsory_task_info = compulsory_task_today[-1]
    else:
      next_compulsory_task_info = None
    next_task_info, next_mobility, is_compulsory_task = GPT.action_selector(cur_time, self.task_place, next_compulsory_task_info, self.persona, self.human_parameters, self.basic_requirements, sunny)
    if is_compulsory_task:
      compulsory_task_today.pop()
    return next_task_info, next_mobility, is_compulsory_task

  def move(self, cur_time, maze, GPT: ActionGenerator, sunny):
      
    """Requirement change"""
    if cur_time.minute % 10 == 0 and cur_time.second == 0:
      if self.task_description == 'sleeping':
        self.basic_requirements['Fullness'] -= 0.10   
      else:
        self.basic_requirements['Fullness'] -= 0.15
        self.basic_requirements['Happiness'] -= 0.05
        self.basic_requirements['Health'] -= 0.05
        self.basic_requirements['Energy'] -= 0.05
        self.basic_requirements['Sociality'] -= 0.10
         
    
    """Sleeping"""
    if self.work_status == True:
      if cur_time >= self.task_end_time:

        """Update agent requirements"""
        for requirement_key in self.task_requirements:
          self.basic_requirements[requirement_key] += float(self.task_requirements[requirement_key])
        self.basic_requirements = requirement_filter(self.basic_requirements)

        """Add memories"""
        """
        if self.task_description != 'sleeping':
          memory = GPT.generate_action_findings(self.task_description, self.task_place, self.persona_prompt)
          # if self.task_data and self.task_data['Importance'] > 0:
          if self.task_data:
            MEM.store_memory(f"{self.name}_self", memory, cur_time)        
        """

        """Select the next action"""
        next_task_data, next_mobility, is_compulsory_task = self.action_selector(cur_time, GPT, sunny)
        if 'Importance' not in next_task_data:
          next_task_data['Importance'] = 0
        if 'Sociality' not in next_task_data:
          next_task_data['Sociality'] = 0
        self.task_data = next_task_data
        
        self.task_requirements = {
          'Fullness': next_task_data['Fullness'], 'Happiness': next_task_data['Happiness'],
          'Health': next_task_data['Health'], 'Energy': next_task_data['Energy'],
          'Sociality': next_task_data['Sociality']
        }

        next_mobility = refresh_mobility(next_mobility)
        self.mobility = next_mobility
        self.mobility_number = 0
        
        if next_mobility==-1:
          """The agent will not move to another place."""
          if is_compulsory_task:
            self.task_end_time = datetime.strptime(next_task_data['end_time'], "%H:%M:%S")
            self.task_end_time.replace(year=cur_time.year, month=cur_time.month, day=cur_time.day)
          else:
            execution_time = next_task_data['execution_time']
            execution_time = datetime.strptime(execution_time, "%H:%M")
            self.task_end_time = cur_time+timedelta(hours=execution_time.hour, minutes=execution_time.minute)

          x_list, y_list = [self.tile[0]], [self.tile[1]]
          self.task_emoji = next_task_data['Emoji']
          self.task_description = next_task_data['Action']

          self.start_conversation = True

        else:
          """The agent will flash to the entrance and start moving."""
          if is_compulsory_task:
            self.task_end_time = datetime.strptime(next_task_data['end_time'], "%H:%M:%S")
            self.task_end_time = self.task_end_time.replace(year=cur_time.year, month=cur_time.month, day=cur_time.day)
          else:
            execution_time = next_task_data['execution_time']
            execution_time = datetime.strptime(execution_time, "%H:%M")
            self.task_end_time = cur_time+timedelta(hours=execution_time.hour, minutes=execution_time.minute)+timedelta(seconds=next_mobility['time_cost']*15)
          

          """Ready for switching to mobility status"""
          self.task_emoji_ready = next_task_data['Emoji']
          self.task_description_ready = next_task_data['Action']
          self.work_status = False
          cur_location_tuple = maze.location_dict[next_mobility['path'][0]]

          x_list, y_list = [cur_location_tuple[1]], [cur_location_tuple[0]]
          self.task_emoji = '🚶‍♂️'
          self.task_description = 'walking'

      else:

        x_list, y_list = [self.tile[0]], [self.tile[1]]

    else:
      x_list, y_list = self.move_mobility(maze)
    
    """Update current place"""
    tile_info = maze.find_tile_attribute(x_list[-1], y_list[-1])
    if tile_info['arena'] != -1:
      self.task_place = tile_info['sector']+':'+tile_info['arena']
    elif tile_info['location'] != -1:
      self.task_place = tile_info['sector']+':'+tile_info['location']
    else:
      self.task_place = tile_info['sector']

    self.basic_requirements = requirement_filter(self.basic_requirements)

    character_movement = {
      'name_initials': self.persona['name_initials'],
      'x_list': x_list,
      'y_list': y_list,
      'pronunciatio': self.task_emoji,
      'description': self.task_description,
      'place': self.task_place,
      'chat': None,
      'requirements': {key: round(value,1) for key, value in self.basic_requirements.items()}
    }
    
    return character_movement
