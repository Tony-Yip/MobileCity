import argparse
import calendar
from datetime import datetime, timedelta
import json
import os
import random
import sys
import time

import asyncio
import pandas as pd

from character.persona import *
from character.agent_memory import AgentMemory
from global_methods import *
from prompt_templates.action_generator import ActionGenerator
from maze import *
from maze.maze import Maze
from mobility_methods import *

class ReverieServer: 
  def __init__(self, sim_code):
    print('Create a server!!')
    self.sim_code = sim_code
    self.sim_folder = f"../frontend_server/storage/{self.sim_code}"
    if os.path.exists(self.sim_folder):
      raise ValueError(f"Sim folder '{sim_code}' exists!")

    self.maze = Maze('city')
    self.action_generator = ActionGenerator(self.maze)
    

  async def start_server(self, args):
    agent_num = args.agent_num
    max_step = args.max_step
    max_api = args.max_api
    is_generate_agent_memory = args.is_generate_agent_memory

    self.n_action = 0
    self.n_conversation = 0

    global_start_time = time.time()
    self.agent_memory = AgentMemory(max_api)
    self.step = 0

    """Start a new simulation. """
    frontend_folder = f"{self.sim_folder}/environment"
    backend_folder = f"{self.sim_folder}/movement"
    self.output_folder = f"{self.sim_folder}/output"
    self.agent_memory.output_folder = self.output_folder 
    traffic_folder = f"{self.output_folder}/traffic"

    """Make the sim folder."""
    if not os.path.exists(self.sim_folder):
      os.mkdir(self.sim_folder)
      os.mkdir(frontend_folder)
      os.mkdir(self.output_folder)
      os.mkdir(backend_folder)
      os.mkdir(traffic_folder)

    """Initialize the current date."""
    date_y, date_m, date_d = int(self.sim_code[:4]), int(self.sim_code[4:6]), int(self.sim_code[6:8])
    day_start_time = datetime(date_y, date_m, date_d, 0, 0, 0)
    cur_time = day_start_time
    is_new_day = True

    """Generate agents."""
    self.persona_dict = dict()
    traffic_flow_hour = {place: 0 for place in self.maze.arena_characters}
    new_env = dict()

    df_wbprofile = pd.read_csv('character/wbprofile_example.csv')
    if agent_num>len(df_wbprofile):
      agent_idxes = random.choices(range(len(df_wbprofile)), k=agent_num) 
    else:
      agent_idxes = random.sample(range(len(df_wbprofile)), agent_num)
    
    agent_cnt = 0
    for agent_idx in agent_idxes:
        agent_cnt += 1
        persona_data = read_df_persona_data(df_wbprofile.iloc[agent_idx])
        persona_data['name'] = f"Agent_{str(agent_cnt).zfill(4)}"
        character = Persona(persona_data)
        self.persona_dict[persona_data['name']] = character
        new_env[persona_data['name']] = {'x': int(persona_data['x']), 'y': int(persona_data['y'])}

        self.agent_memory.create_index(f"{persona_data['name']}_self")

    with open(f"{self.sim_folder}/0.json", 'w') as new_env_file:
      new_env_file.write(json.dumps(new_env, indent=2))

    persona_name_list = list(new_env.keys())

    for character in self.persona_dict.values():
      character.initialize_modules(persona_name_list)

    while self.step < max_step:
      print(f"\r{self.step}/{max_step}", end='', flush=True)

      """If the time is 0:00 now, start a new day"""
      if is_new_day==False:
        def is_midnight(cur_time):
          return cur_time.hour == 0 and cur_time.minute == 0 and cur_time.second == 0
        is_new_day = is_midnight(cur_time)      
      
      if is_new_day:
        """Generate agents"""
        for persona_name in persona_name_list:
          character = self.persona_dict[persona_name]
          character.persona['date'] = f"{calendar.month_name[date_m]} {date_d}, {date_y}, {calendar.day_name[cur_time.weekday()]}"
          character.initialize_compulsory_task(cur_time)

        """Change weather"""
        sunny = random.choice([True, False])
        if sunny:
          weather = '🌞 SUNNY'
        else:
          weather = '🌧️ RAINY'        
        is_new_day=False

      cur_time_str = cur_time.strftime("%H:%M:%S")
      cur_time_movements = f"{calendar.month_name[cur_time.month]} {cur_time.day}, {cur_time.year}, {cur_time_str}, {calendar.day_name[cur_time.weekday()]}"
      movements = {'persona': {}, 'meta': {'cur_time': cur_time.strftime("%Y/%m/%d %H:%M:%S"), 'weather': weather}}

      for persona_name in persona_name_list:
        character = self.persona_dict[persona_name]

        if character.task_place in self.maze.arena_characters:
          try:
            self.maze.arena_characters[character.task_place].remove(persona_name)
          except:
            pass
        
        """Add action memories"""
        if is_generate_agent_memory:
          if character.work_status == True and cur_time >= character.task_end_time and character.task_description != 'sleeping' and character.task_data:
            await self.agent_memory.generate_action_memory(character.name, character.task_description, character.task_place, character.persona_prompt, cur_time)
            self.n_action += 1

        character_movement = character.move(cur_time, self.maze, self.action_generator, sunny)
        movements['persona'][persona_name] = character_movement

        if character.task_place in self.maze.arena_characters:
          self.maze.arena_characters[character.task_place].add(character.name)

        """When the agent enters a new place, it may start a conversation"""
        if character.task_description!='sleeping' and character.start_conversation and not character.in_conversation and random.random() < 1:
          talk_person = self.perceive(character, cur_time)
          if talk_person!=-1:
            another_character = self.persona_dict[talk_person]
            self.update_conversation_state(character, another_character, cur_time, False)
            self.n_conversation += 1

          character.start_conversation = False

        """If the agent feels lonely, it will talk with other agents on call"""
        if character.basic_requirements['Sociality'] <= 2 and not character.in_conversation and character.task_description != 'sleeping' and random.random() < 0.2:
          talk_person = self.perceive_remote(character, cur_time)
          if talk_person!=-1:
            another_character = self.persona_dict[talk_person]
            self.update_conversation_state(character, another_character, cur_time, True)   
            self.n_conversation += 1

        if character.current_chat:
          if cur_time >= character.conversation_end_time:
            another_character = self.persona_dict[character.conversation_partner]
            another_character.in_conversation = False
            character.in_conversation = False
            character.is_remote_chat = False
            another_character.is_remote_chat = False
            character.conversation_partner = None
            character.conversation_end_time = None
            character.current_chat = None

        if character.in_conversation:
          if character.is_remote_chat:
            movements['persona'][persona_name]['pronunciatio'] += ' 📞'
          else:
            movements['persona'][persona_name]['pronunciatio'] += ' 🗣️'

      curr_move_file = f"{backend_folder}/{self.step}.json"
      with open(curr_move_file, "w") as outfile: 
        outfile.write(json.dumps(movements, indent=2))
      new_env = dict()
      for persona_name in persona_name_list:
        new_env[persona_name] = {'x': movements['persona'][persona_name]['x_list'][-1], 'y': movements['persona'][persona_name]['y_list'][-1]}

      """Update traffic_flow"""
      for place in traffic_flow_hour:
        traffic_flow_hour[place] += len(self.maze.arena_characters[place])
      if cur_time.minute == 59 and cur_time.second == 45:
        curr_traffic_file = f"{traffic_folder}/{self.step}.json"
        with open(curr_traffic_file, "w") as outfile: 
          traffic_flow = {
            'time': cur_time_movements,
            'traffic_flow': {place: flow/240 for place, flow in traffic_flow_hour.items()},
            'cost': time.time()-global_start_time
          }
          outfile.write(json.dumps(traffic_flow, indent=2))
        traffic_flow_hour = {place: 0 for place in self.maze.arena_characters}

      self.step += 1
      cur_time = cur_time + timedelta(seconds=15)
    if is_generate_agent_memory:
      await self.agent_memory.finish_everything()
    self.action_generator.generate_log(self.sim_code)
    print('\n')
    print(self.n_action)
    print(self.n_conversation)
    print('Finish simulation!')

  def perceive_remote(self, character, cur_time):
    conversation_end_time = cur_time + timedelta(minutes=10)
    talk_person = random.choice(list(self.persona_dict.keys()))
    another_character = self.persona_dict[talk_person]
    if another_character.name != character.name and another_character.in_conversation==False and another_character.task_description!='sleeping' and conversation_end_time<=another_character.task_end_time:
      return talk_person
    else:
      return -1    

  def perceive(self, character, cur_time):
    if character.task_place not in self.maze.arena_characters: return -1
    if len(self.maze.arena_characters[character.task_place]) == 1: return -1
    """Choose one person to chat with"""
    conversation_end_time = cur_time + timedelta(minutes=10)
    talk_person = random.choice(list(self.maze.arena_characters[character.task_place]))
    another_character = self.persona_dict[talk_person]
    if another_character.name != character.name and another_character.in_conversation==False and another_character.task_description!='sleeping' and conversation_end_time<=another_character.task_end_time:
      return talk_person
    else:
      return -1
    
  def update_conversation_state(self, characterA, characterB, cur_time, is_remote):
    """Change conversation status"""
    characterA.in_conversation = True
    characterB.in_conversation = True
    characterA.is_remote_chat = is_remote
    characterB.is_remote_chat = is_remote
    characterA.current_chat = f"(Speaking with {characterB.name})"
    characterB.current_chat = f"(Speaking with {characterA.name})"
    characterA.conversation_partner = characterB.name
    characterA.conversation_end_time = cur_time + timedelta(minutes=10)
    characterB.conversation_partner = characterA.name
    characterB.conversation_end_time = cur_time + timedelta(minutes=10)
    characterA.basic_requirements['Sociality'] += 2
    characterB.basic_requirements['Sociality'] += 2
    return
  

if __name__ == '__main__':
  os.chdir(os.path.dirname(os.path.abspath(__file__)))
  start_time = time.time()
  timestamp = int(datetime.now().timestamp())

  parser = argparse.ArgumentParser(description="Start simulation!")
  parser.add_argument('--start_date', type=str, required=False, default='20250908', help='The start date of the experiment.')
  parser.add_argument('--agent_num', type=str, required=False, default=1, help='The number of agents.')  
  parser.add_argument('--max_step', type=int, required=False, default=5760, help='The maximum number of simulation steps. For simulation in one day, the max step is 5760.')
  parser.add_argument('--max_api', type=int, required=False, default=1, help='The maximum number of concurrent API requests.')
  parser.add_argument('--is_generate_agent_memory', type=bool, required=False, default=False, help='Whether to generate agent memory.')
  args = parser.parse_args()

  try:
      datetime.strptime(args.start_date, '%Y%m%d')
  except ValueError:
      print('Please enter a correct start date. (Eg. 20250908)')
      sys.exit()

  simcode = f"{args.start_date}_{args.agent_num}_{timestamp}"
  print(f"Start the simulation: {simcode}")
  rs = ReverieServer(simcode)
  asyncio.run(rs.start_server(args))
  print(f"Time cost in simulation: {time.time()-start_time}")
  print('Finish simulation!')