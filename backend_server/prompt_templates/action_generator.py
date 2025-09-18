from datetime import datetime, timedelta
import json
import os

import numpy as np
import pandas as pd
import re
from scipy.spatial.distance import cosine


from global_methods import *

class ActionGenerator:
    def __init__(self, maze):
        """
        is_GPU -- True: use model
        """
        self.prompt_dir = 'prompt_templates/v3/'
        self.max_tries = 5
        self.maze = maze
        self.load_mobility_data()
        self.load_action_df()
        self.token_count = 0
    
    def load_action_df(self):
        """Load action csv files."""
        df_Meal = pd.read_csv('character/actions/Meal.csv')
        df_Entertainment = pd.read_csv('character/actions/Entertainment.csv')
        df_Exercise = pd.read_csv('character/actions/Exercise.csv')
        df_Relaxation = pd.read_csv('character/actions/Relaxation.csv')
        
        """Map a place to a location."""
        with open ('maze/action_map.json', 'r') as json_file:
            action_map = json.load(json_file)
        
        def real_action_place(fake_place):
            if fake_place in action_map:
                return f"{action_map[fake_place]['sector']}:{action_map[fake_place]['arena']}"
            elif fake_place in ['Home', 'Convenience Store', 'Company Canteen']:
                return fake_place
            else:
                raise ValueError('Drink beer!')

        df_Meal['Original_Place'] = df_Meal['Place']
        df_Entertainment['Original_Place'] = df_Entertainment['Place']
        df_Exercise['Original_Place'] = df_Exercise['Place']
        df_Relaxation['Original_Place'] = df_Relaxation['Place']
        df_Meal['Place'] = df_Meal['Place'].apply(real_action_place)
        df_Entertainment['Place'] = df_Entertainment['Place'].apply(real_action_place)
        df_Exercise['Place'] = df_Exercise['Place'].apply(real_action_place)
        df_Relaxation['Place'] = df_Relaxation['Place'].apply(real_action_place)

        self.action_requirements_dict = {
            'Meal': df_Meal, 'Entertainment': df_Entertainment, 'Exercise': df_Exercise, 'Relaxation': df_Relaxation
        }

        real_action_map = dict()
        fake_action_map = dict()
        for place, s_a in action_map.items():
            fake_action_map[place] = f"{s_a['sector']}:{s_a['arena']}"
            if s_a['arena']=='Restaurant':
                place = place.split(': ')[1]+' Restaurant'
            elif s_a['arena']=='Park':
                place = place.split(': ')[1]
            real_action_map[f"{s_a['sector']}:{s_a['arena']}"] = place
            
        self.action_map = real_action_map
        self.fake_action_map = fake_action_map

        """Add multiple entrances to the same places."""
        self.multiple_entrance_dict = {
            'Convenience Store': [
                'Company A:Convenience Store:0', 'Company A:Convenience Store:1',
                'Company B:Convenience Store:0', 'Company B:Convenience Store:1',
                'Apartment B:Convenience Store:0', 'Apartment B:Convenience Store:1',
                'Apartment D:Convenience Store:0', 'Apartment D:Convenience Store:1',
                'Apartment E:Convenience Store:0', 'Apartment E:Convenience Store:1',
                'Apartment G:Convenience Store:0', 'Apartment G:Convenience Store:1',
                'Department Store:Convenience Store'
            ],
            'Company A:Convenience Store': [
                'Company A:Convenience Store:0', 'Company A:Convenience Store:1'
            ],
            'Company B:Convenience Store': [
                'Company B:Convenience Store:0', 'Company B:Convenience Store:1'
            ],
            'Apartment B:Convenience Store': [
                'Apartment B:Convenience Store:0', 'Apartment B:Convenience Store:1'
            ],
            'Apartment D:Convenience Store': [
                'Apartment D:Convenience Store:0', 'Apartment D:Convenience Store:1'
            ],
            'Apartment E:Convenience Store': [
                'Apartment E:Convenience Store:0', 'Apartment E:Convenience Store:1'
            ],
            'Apartment G:Convenience Store': [
                'Apartment G:Convenience Store:0', 'Apartment G:Convenience Store:1'
            ],
            'Apartment A:Concert Hall': [
                'Apartment A:Concert Hall:0', 'Apartment A:Concert Hall:1'
            ],
            'Apartment H:Community Center': [
                'Apartment H:Community Center:0', 'Apartment H:Community Center:1'
            ],
            'Company B:Office A': [
                'Company B:Office A:0', 'Company B:Office A:1'
            ],
            'Company B:Office C': [
                'Company B:Office C:0', 'Company B:Office C:1'
            ],
            'Hospital:Hospital': [
                'Hospital:Hospital:0', 'Hospital:Hospital:1'
            ]
        }
        
        with open('character/actions/place_description.txt', 'r') as place_description_file:
            place_description_content = place_description_file.read()

        place_description_content = place_description_content.split('\n')
        self.place_description_dict = dict()
        for i in range(len(place_description_content)//2):
            place = place_description_content[2*i][2:]
            description = place_description_content[2*i+1][3:]
            self.place_description_dict[place] = description

        self.requirement_feeling_dict = {
            "Fullness": {
                0: "Extremely hungry",  # Extreme hunger, urgent need for food
                1: "Very hungry",  # Strong hunger pangs
                2: "Moderately hungry",  # Clear desire for food
                3: "Slightly hungry",  # Beginning to feel hunger
                4: "Neither hungry nor full",  # Neutral fullness
                5: "Somewhat full",  # Just started feeling content
                6: "Comfortably full",  # Good level of fullness
                7: "Very full",  # High level of fullness
                8: "Extremely full",  # Almost at maximum capacity
                9: "Completely full",  # Maximum fullness, cannot eat more
                10: "Completely full"
            },
            
            "Happiness": {
                0: "Severely unhappy",  # Deep despair or depression
                1: "Very unhappy",  # Strongly negative emotions
                2: "Moderately unhappy",  # Clear negative mood
                3: "Slightly unhappy",  # Mild negative feelings
                4: "Neutral mood",  # Neither happy nor unhappy
                5: "Slightly happy",  # Mild positive mood
                6: "Moderately happy",  # Clear positive emotions
                7: "Very happy",  # Strong positive feelings
                8: "Extremely happy",  # Great joy and satisfaction
                9: "Maximally happy",  # Peak happiness and joy
                10: "Maximally happy"
            },
            
            "Health": {
                0: "Critical health condition",  # Severe health issues
                1: "Very poor health",  # Multiple serious health problems
                2: "Poor health",  # Significant health issues
                3: "Below average health",  # Some health concerns
                4: "Fair health",  # Basic health functioning
                5: "Moderate health",  # Generally okay health
                6: "Good health",  # Above average health
                7: "Very good health",  # Strong health condition
                8: "Excellent health",  # Peak physical condition
                9: "Perfect health",  # Optimal health state
                10: "Perfect health"
            },
            
            "Energy": {
                0: "Completely exhausted",  # No energy left
                1: "Very low energy",  # Barely able to function
                2: "Low energy",  # Clear energy deficit
                3: "Slightly tired",  # Below average energy
                4: "Normal energy",  # Average energy levels
                5: "Moderately energetic",  # Above average energy
                6: "Energetic",  # Good energy levels
                7: "Very energetic",  # High energy state
                8: "Extremely energetic",  # Abundant energy
                9: "Maximum energy",  # Peak energy levels
                10: "Maximum energy"
            },
            
            "Sociality": {
                0: "Completely isolated",  # Total social withdrawal
                1: "Very socially isolated",  # Strong feeling of isolation
                2: "Socially disconnected",  # Clear lack of social connection
                3: "Slightly socially withdrawn",  # Mild social disconnection
                4: "Neutral social state",  # Basic social balance
                5: "Somewhat social",  # Mild social satisfaction
                6: "Socially active",  # Good social interaction
                7: "Very socially active",  # Strong social connections
                8: "Extremely social",  # Excellent social fulfillment
                9: "Maximum social fulfillment",  # Peak social satisfaction
                10: "Maximum social fulfillment"
            }
        }

        self.relationship_feeling_dict = {
            "familiarity": {
                0: "completely unacquainted with",  # A feels completely unacquainted with B
                1: "extremely distant from",  # A feels extremely distant from B
                2: "very distant from",  # A feels very distant from B
                3: "moderately distant from",  # A feels moderately distant from B
                4: "slightly distant from",  # A feels slightly distant from B
                5: "somewhat close to",  # A feels somewhat close to B
                6: "moderately close to",  # A feels moderately close to B
                7: "quite close to",  # A feels quite close to B
                8: "very close to",  # A feels very close to B
                9: "extremely close to",  # A feels extremely close to B
                10: "deeply connected to",  # A feels deeply connected to B
            },
            
            "affinity": {
                0: "extremely hostile towards",  # A feels extremely hostile towards B
                1: "very hostile towards",  # A feels very hostile towards B
                2: "moderately hostile towards",  # A feels moderately hostile towards B
                3: "slightly hostile towards",  # A feels slightly hostile2 towards B
                4: "indifferent towards",  # A feels indifferent towards B
                5: "neutral towards",  # A feels neutral towards B
                6: "somewhat friendly towards",  # A feels somewhat friendly towards B
                7: "quite friendly towards",  # A feels quite friendly towards B
                8: "very fond of",  # A feels very fond of B
                9: "extremely fond of",  # A feels extremely fond of B
                10: "deeply attached to",  # A feels deeply attached to B
            }
        }

    def load_mobility_data(self):

        mobility_data = {}
        mobility_data['sunny'] = pd.read_csv('character/actions/sunny_choice_filtered.csv')
        mobility_data['rainy'] = pd.read_csv('character/actions/rainy_choice_filtered.csv')
        self.mobility_data = mobility_data
    
    def action_selector(self, cur_time: datetime, cur_place, next_compulsory_task_info, persona, human_parameters, basic_requirements, sunny):
        """The inputs.
        cur_time: current time
        task_memory: tasks that the agent must perform
        persona: the personality of the agent
        basic_requirements: the changing basic requirements of the agent
        """

        if basic_requirements['Fullness'] < 4:
            action_category = 'Meal'
        elif basic_requirements['Health'] < 4:
            action_category = 'Exercise'
        elif basic_requirements['Energy'] < 4:
            action_category = 'Relaxation'
        elif basic_requirements['Happiness'] < 4:
            action_category = 'Entertainment'
        else:
            action_cats = ['Fullness', 'Health', 'Energy', 'Happiness']
            requirements = [basic_requirements[cat] for cat in action_cats]
            action_index = requirements.index(min(requirements))
            action_cats = ['Meal', 'Exercise', 'Relaxation', 'Entertainment']
            action_category = action_cats[action_index]
            
        action_df = self.action_requirements_dict[action_category].copy()

        """Filter 1: Canteen"""
        if action_category=='Meal' or action_category=='Relaxation':
            if cur_time.weekday() >= 5 or not persona["working_place"] or not persona["working_place"].startswith('Company'):
                action_df = action_df[action_df['Place']!='Company Canteen']        

        """Filter 2: Start Time of Next Task"""
        action_df['EarliestStartTime'] = pd.to_datetime(action_df['EarliestStartTime'], format='%H:%M').apply(
            lambda x: x.replace(year=cur_time.year, month=cur_time.month, day=cur_time.day)
        )
        action_df['LatestStartTime'] = pd.to_datetime(action_df['LatestStartTime'], format='%H:%M').apply(
            lambda x: x.replace(year=cur_time.year, month=cur_time.month, day=cur_time.day)
        )

        def cal_cur_punctuality(cur_place, next_place, earliest_start_time, latest_start_time):
            if next_place == 'Home':
                next_place = persona['living_area']
            elif next_place == 'Company Canteen':
                next_place = persona['working_place'].split(':')[0]+':Company Canteen'
            
            if next_place not in self.multiple_entrance_dict:
                next_entrances = [next_place]
            else:
                next_entrances = self.multiple_entrance_dict[next_place]
            if cur_place not in self.multiple_entrance_dict:
                cur_entrances = [cur_place]
            else:
                cur_entrances = self.multiple_entrance_dict[cur_place]

            fastest_time = float('inf')
            closest_next_entrance = ''
            closest_cur_entrance = ''
            for cur_entrance in cur_entrances:
                for next_entrance in next_entrances:
                    cur_mobility_path = self.maze.get_fastest_path(cur_entrance, next_entrance)
                    cur_mobility_time = max(cur_mobility_path[1])
                    if cur_mobility_time<fastest_time:
                        closest_next_entrance = next_entrance
                        closest_cur_entrance = cur_entrance
                        fastest_time = cur_mobility_time
            
            real_start_time = cur_time+timedelta(seconds=fastest_time*15)

            return closest_next_entrance, closest_cur_entrance, real_start_time, (real_start_time>=earliest_start_time) & (real_start_time<=latest_start_time)
        
        action_df[['Place', 'RealStartPlace', 'RealStartTime', 'CurPunctuality']] = action_df.apply(lambda row: cal_cur_punctuality(cur_place, row['Place'], row['EarliestStartTime'], row['LatestStartTime']), axis=1, result_type='expand')
        action_df = action_df[action_df['CurPunctuality']==True]


        """Filter 3: Start Time of Compulsory Task"""
        if next_compulsory_task_info:
            if action_df.empty:
                """Conduct compulsory task"""
                if cur_place in self.multiple_entrance_dict: cur_place = self.multiple_entrance_dict[cur_place][0]
                if next_compulsory_task_info['Place'] in self.multiple_entrance_dict: next_compulsory_task_info['Place'] = self.multiple_entrance_dict[next_compulsory_task_info['Place']][0]
                next_mobility = self.route_generator(cur_place, next_compulsory_task_info['Place'], persona['cat'], sunny)
                return next_compulsory_task_info, next_mobility, True
            post_place = next_compulsory_task_info['Place']
            post_start_time = next_compulsory_task_info['start_time']
            post_start_time = datetime.strptime(post_start_time, "%H:%M:%S")
            post_start_time = post_start_time.replace(year=cur_time.year, month=cur_time.month, day=cur_time.day)

            def cal_nxt_punctuality(cur_place, next_place, real_start_time, execution_time):
                real_post_place = post_place
                if real_post_place == 'Home':
                    real_post_place = persona['living_area']
                elif real_post_place == 'Company Canteen':
                    real_post_place = persona['working_place'].split(':')[0]+':Company Canteen'

                execution_time = datetime.strptime(execution_time, "%H:%M")

                if real_post_place not in self.multiple_entrance_dict:
                    next_mobility_path = self.maze.get_fastest_path(next_place, real_post_place)
                    next_mobility_time = min(next_mobility_path[1])
                    arrive_time = real_start_time+timedelta(hours=execution_time.hour, minutes=execution_time.minute)+timedelta(seconds=next_mobility_time*15)
                else:
                    closest_entrance = ''
                    fastest_time = float('inf')
                    if cur_place in self.multiple_entrance_dict: cur_place = self.multiple_entrance_dict[cur_place][0]
                    for entrance in self.multiple_entrance_dict[real_post_place]:
                        cur_mobility_path = self.maze.get_fastest_path(cur_place, entrance)
                        cur_mobility_time = min(cur_mobility_path[1])
                        if cur_mobility_time<fastest_time:
                            closest_entrance = entrance
                            fastest_time = cur_mobility_time
                    arrive_time = real_start_time+timedelta(hours=execution_time.hour, minutes=execution_time.minute)+timedelta(seconds=fastest_time*15)
                    real_post_place = closest_entrance

                return real_post_place, True if arrive_time<=post_start_time else False

            action_df[['PostPlace', 'NxtPunctuality']] = action_df.apply(lambda row: cal_nxt_punctuality(cur_place, row['Place'], row['RealStartTime'], row['ShortestExecutionTime']), axis=1, result_type='expand')
            action_df = action_df[action_df['NxtPunctuality']==True]
            if action_df.empty:
                """Conduct compulsory task"""
                if cur_place in self.multiple_entrance_dict: cur_place = self.multiple_entrance_dict[cur_place][0]
                if next_compulsory_task_info['Place'] in self.multiple_entrance_dict: next_compulsory_task_info['Place'] = self.multiple_entrance_dict[next_compulsory_task_info['Place']][0]
                next_mobility = self.route_generator(cur_place, next_compulsory_task_info['Place'], persona['cat'], sunny)
                return next_compulsory_task_info, next_mobility, True
        
        """Filter 4: Similarity"""

        if action_category=='Meal':
            hp_indexes = [0, 1, 2, 3]
        if action_category=='Entertainment':
            hp_indexes = [4, 5, 6, 7]
        if action_category=='Exercise':
            hp_indexes = [8, 9, 10, 11]
        else:
            hp_indexes = [12, 13, 14, 15]
        hp_agent = np.array([human_parameters[index] for index in hp_indexes])

        def cal_hp_similarity(hp0, hp1, hp2, hp3):
            hp_action = np.array([hp0, hp1, hp2, hp3])
            # return 1-cosine(hp_agent, hp_action)
            return 1/(1+np.linalg.norm(hp_agent - hp_action))

        columns_hp = action_df.columns[9:13]
        action_df['Similarity'] = action_df.apply(lambda row: cal_hp_similarity(*(row[col] for col in columns_hp)), axis=1)
        top_5_actions = action_df.nlargest(5, 'Similarity')

        if action_df.empty:
            """Conduct compulsory task"""
            next_mobility = self.route_generator(cur_place, next_compulsory_task_info['Place'], persona['cat'], sunny)
            return None, next_mobility, True
        else:
            """Let GPT choose one action"""

            """
            def generate_persona_prompt(persona):
                employment_dict = {'0': 'Unemployed', '1': 'Employed', '2': 'Part-time Work'}
                income_dict = {'0': 'Medium', '1': 'High'}
                persona_prompt = f"Name: {persona['name']}\nGender: {persona['gender']}\nAge: {persona['age']}\nJob: {employment_dict[persona['cat'][1]]}\nIncome: {income_dict[persona['cat'][2]]}\nCharacter: {persona['character']}"
                return persona_prompt
            persona_prompt = generate_persona_prompt(persona)

            def generate_action_prompt(top_5_actions):
                action_prompt = 'action_number,action,place\n'
                actions = top_5_actions['Action'].tolist()
                places = top_5_actions['Original_Place'].tolist()
                for i in range(len(actions)):
                    action_prompt += f"{i},{actions[i]},{places[i]}\n"
                return action_prompt
            action_prompt = generate_action_prompt(top_5_actions)

            def generate_place_prompt(top_5_actions):
                place_prompt = ''
                place_set = set(top_5_actions['Original_Place'].tolist())
                for place in place_set:
                    place_prompt += f"- {place}\n-- {self.place_description_dict[place]}\n"
                return place_prompt
            place_prompt = generate_place_prompt(top_5_actions)

            def generate_prompt(persona_prompt, action_prompt, place_prompt, cur_time):
                time_prompt = f"{str(cur_time.hour).zfill(2)}:{str(cur_time.minute).zfill(2)}"
                prompt_file = self.prompt_dir + '1_1_vote_action.txt'
                with open(prompt_file, 'r') as f:
                    prompt_content = f.read()
                prompt_content = prompt_content.replace('!<INPUT 0>!', persona_prompt)
                prompt_content = prompt_content.replace('!<INPUT 1>!', action_prompt)
                prompt_content = prompt_content.replace('!<INPUT 2>!', place_prompt)
                prompt_content = prompt_content.replace('!<INPUT 3>!', time_prompt)
                return prompt_content
            prompt_content = generate_prompt(persona_prompt, action_prompt, place_prompt, cur_time)
            # print(prompt_content)
            """

            action_vote = top_5_actions['Similarity'].tolist()
            action_vote = [vote/sum(action_vote) for vote in action_vote]
            action_choice = np.random.choice([i for i in range(len(action_vote))], p=action_vote)

            """
            is_valid = False
            for _ in range(self.max_tries):
                action_choice = self.ask_llm(prompt_content)
                if action_choice in [str(i) for i in range(5)]:
                    action_choice = int(action_choice)
                    is_valid = True
                    break
            if not is_valid:
                raise ValueError(f"Wrong action choice: {action_choice}")
            """

            next_task_data = top_5_actions.iloc[action_choice]
            next_task_info = {
                'Action': next_task_data['Action'],
                'Place': next_task_data['Place'],
                'Fullness': next_task_data['Fullness'],
                'Happiness': next_task_data['Happiness'],
                'Health': next_task_data['Health'],
                'Energy': next_task_data['Energy'],
                'Emoji': next_task_data['Emoji'],
                'execution_time': next_task_data['ShortestExecutionTime'],
                'Importance': next_task_data['Importance']
            }
            
            if cur_place == next_task_data['Place']:
                return next_task_info, -1, False
            else:
                next_mobility = self.route_generator(next_task_data['RealStartPlace'], next_task_data['Place'], persona['cat'], sunny)
                return next_task_info, next_mobility, False
    
    """
    def generate_next_action_category(self, cur_time: datetime, persona, basic_requirements, next_compulsory_task_info):
        
        cur_time_str = cur_time.strftime("%H:%M:%S")

        persona_prompt = f"Name: {persona['name']}\nGender: {persona['gender']}\nAge: {persona['age']}\nCharacter: {persona['character']}"
        basic_requirements_prompt = f"Fullness: {basic_requirements['Fullness']}\nHappiness: {basic_requirements['Happiness']}\nHealth: {basic_requirements['Health']}\nEnergy: {basic_requirements['Energy']}"
        
        if next_compulsory_task_info is not None:
            next_task_prompt = f"Task: {next_compulsory_task_info['Action']}\nFullness: {next_compulsory_task_info['Fullness']}\nHappiness: {next_compulsory_task_info['Happiness']}\nHealth: {next_compulsory_task_info['Health']}\nEnergy: {next_compulsory_task_info['Energy']}\nTime: {next_compulsory_task_info['start_time']}"
        else:
            next_task_prompt = "No compulsory task"

        def generate_prompt():
            prompt_file = self.prompt_dir + '1_0_next_action.txt'
            with open(prompt_file, 'r') as f:
                prompt_content = f.read()
            prompt_content = prompt_content.replace('!<INPUT 0>!', persona_prompt)
            prompt_content = prompt_content.replace('!<INPUT 1>!', basic_requirements_prompt)
            prompt_content = prompt_content.replace('!<INPUT 2>!', next_task_prompt)
            prompt_content = prompt_content.replace('!<INPUT 3>!', cur_time_str)

            return prompt_content
        
        def is_valid(action_category):
            return action_category in ['Meal', 'Entertainment', 'Exercise', 'Relaxation']

        
        prompt_content = generate_prompt()
        
        for _ in range(self.max_tries):
            output_gen = self.client.chat.completions.create(
                model="gpt-4o", # gpt-4, gpt-4o, text-embedding-3-small, text-embedding-3-large
                messages=[
                    {"role": "user", "content": prompt_content}
                ],
                max_tokens=5,
                temperature=1
            )

            choice = output_gen.choices[0]
            action_category = choice.message.content

            if is_valid(action_category):
                return action_category
        
        raise ValueError(f"Wrong action category: \n{action_category}")
    """

    def route_generator(self, cur_place, next_place, cat, sunny):

        if cur_place in self.multiple_entrance_dict:
            final_path, final_time_cost = '', float('inf')
            for entrance in self.multiple_entrance_dict[cur_place]:
                path, time_cost = self.route_generator(entrance, next_place, cat, sunny)
                if time_cost < final_time_cost:
                    final_time_cost = time_cost
                    final_path = path
            return final_path, final_time_cost
        paths, _, walking_time_costs, onboard_time_costs, money_costs = self.maze.get_fastest_path(cur_place, next_place)

        if sunny:
            user_csv = self.mobility_data['sunny'].copy()
        else:
            user_csv = self.mobility_data['rainy'].copy()
        user_csv = user_csv[user_csv['CAT']==int(cat)]

        def cal_l2_similarity(user_data, cur_data):
            user_data = np.array(user_data)
            # return 1-cosine(user_data, cur_data)
            return 1/(1+np.linalg.norm(user_data - cur_data))
        
        if walking_time_costs[1] == float('inf'):
            if walking_time_costs[2] == float('inf'):
                transportaion_choice = 0
                path = paths[0]
                time_cost = walking_time_costs[0]
            else:
                cur_data = np.array([0, walking_time_costs[2], onboard_time_costs[2], money_costs[2], 0, walking_time_costs[0], onboard_time_costs[0], money_costs[0]])
                csv_columns = user_csv.columns[list(range(1,5))+list(range(9,13))]
                user_csv['Similarity'] = user_csv.apply(lambda row: cal_l2_similarity([row[col] for col in csv_columns], cur_data), axis=1)
                top_mobility_data = user_csv.nlargest(1, 'Similarity')
                top_mobility_vote = [top_mobility_data[choice].values[0] for choice in ['CHOICE_0', 'CHOICE_2']]
                try:
                    top_mobility_vote = [vote/sum(top_mobility_vote) for vote in top_mobility_vote]
                    transportaion_choice = np.random.choice([0,2], p=top_mobility_vote)
                except:
                    transportaion_choice = 0
                path = paths[transportaion_choice]
                time_cost = walking_time_costs[transportaion_choice]                    
        else:
            if walking_time_costs[2] == float('inf'):
                cur_data = np.array([0, walking_time_costs[1], onboard_time_costs[1], money_costs[1], 0, walking_time_costs[0], onboard_time_costs[0], money_costs[0]])
                csv_columns = user_csv.columns[5:13]
                user_csv['Similarity'] = user_csv.apply(lambda row: cal_l2_similarity([row[col] for col in csv_columns], cur_data), axis=1)
                user_csv.loc[:, 'Similarity'] = user_csv.apply(
                    lambda row: cal_l2_similarity([row[col] for col in csv_columns], cur_data), 
                    axis=1
                )
                top_mobility_data = user_csv.nlargest(1, 'Similarity')
                top_mobility_vote = [top_mobility_data[choice].values[0] for choice in ['CHOICE_0', 'CHOICE_1']]
                try:
                    top_mobility_vote = [vote/sum(top_mobility_vote) for vote in top_mobility_vote]
                    transportaion_choice = np.random.choice(2, p=top_mobility_vote)
                except:
                    transportaion_choice = 0
                path = paths[transportaion_choice]
                time_cost = walking_time_costs[transportaion_choice]                             
            else:
                cur_data = np.array([0, walking_time_costs[2], onboard_time_costs[2], money_costs[2], 0, walking_time_costs[1], onboard_time_costs[1], money_costs[1], 0, walking_time_costs[0], onboard_time_costs[0], money_costs[0]])
                csv_columns = user_csv.columns[1:13]
                user_csv['Similarity'] = user_csv.apply(lambda row: cal_l2_similarity([row[col] for col in csv_columns], cur_data), axis=1)
                top_mobility_data = user_csv.nlargest(1, 'Similarity')
                top_mobility_vote = [top_mobility_data[choice].values[0] for choice in ['CHOICE_0', 'CHOICE_1', 'CHOICE_2']]
                try:
                    top_mobility_vote = [vote/sum(top_mobility_vote) for vote in top_mobility_vote]
                    transportaion_choice = np.random.choice(3, p=top_mobility_vote)
                except:
                    transportaion_choice = 0
                path = paths[transportaion_choice]
                time_cost = walking_time_costs[transportaion_choice]
        return path, time_cost

    def replace_inputs(self, prompt_content, replacements):
        return re.sub(r'!<INPUT\s+(\d+)>!', 
                    lambda m: replacements.get(m.group(1), m.group(0)), 
                    prompt_content)

    def generate_log(self, simcode):

        def transfer_place(task_place):
            if task_place in self.action_map:
                task_place = self.action_map[task_place]
            return task_place

        dir_name = f"../frontend_server/storage/{simcode}"

        output = {}

        """Initialization"""
        file_name = f"{dir_name}/movement/0.json"
        with open(file_name) as file:
            data = json.load(file)
            output['weather'] = data['meta']['weather']
            output['persona'] = {}
            for character in data['persona']:
                output['persona'][character] = {'action': [{'action': 'dummy', 'end_time': 'dummy'}],
                                                'basic needs': [],
                                                'chat': [{'chat': None, 'end_time': 'dummy'}]}

        """Loop"""
        i = 0
        while True:
            file_name = f"{dir_name}/movement/{i}.json"
            if os.path.exists(file_name):
                with open(file_name) as file:
                    data = json.load(file)
                    # cur_time = ','.join(data['meta']['cur_time'].split(',')[:-1])
                    cur_time = data['meta']['cur_time']
                    for character in data['persona']:

                        """OUTPUT 1: Action"""

                        # if data['persona'][character]['description'] in ['walking', 'on the PMV', 'on the bus']: continue

                        if data['persona'][character]['description'] != output['persona'][character]['action'][-1]['action']:
                            new_action = {
                                'action': data['persona'][character]['description'],
                                'start_time': cur_time[:-3],
                                'end_time': cur_time[:-3],
                                'place': transfer_place(data['persona'][character]['place'])
                            }
                            output['persona'][character]['action'].append(new_action)
                        else:
                            output['persona'][character]['action'][-1]['end_time'] = cur_time[:-3]

                        
                        """OUTPUT 2: Conversation"""
                        """
                        if data['persona'][character]['chat']: 
                            if data['persona'][character]['chat'] != output['persona'][character]['chat'][-1]['chat'] and data['persona'][character]['chat'] != '(Speaking)':
                                new_chat = {
                                    'chat': data['persona'][character]['chat'],
                                    'start_time': cur_time,
                                    'end_time': cur_time,
                                    'place': transfer_place(data['persona'][character]['place'])
                                }
                                output['persona'][character]['chat'].append(new_chat)
                            else:
                                output['persona'][character]['chat'][-1]['end_time'] = cur_time                        
                        """

                        """OUTPUT 3: Basic Needs"""
                        if cur_time[-5:] == '00:00':
                            new_basic_needs = {
                                'time': cur_time,
                                'basic needs': data['persona'][character]['requirements']
                            }
                            output['persona'][character]['basic needs'].append(new_basic_needs)
            else:
                break
            i += 1

        """To delete dummy files"""
        for character in output['persona']:
            actions = output['persona'][character]['action']
            output['persona'][character]['action'] = actions[1:]
            chats = output['persona'][character]['chat']
            output['persona'][character]['chat'] = chats[1:]

        with open(f"{dir_name}/output/actions.json", "w") as outfile:
            outfile.write(json.dumps(output, indent=2))
        
        return output

if __name__ == '__main__':
    # maze = Maze('City')
    # GPT = GPT_caller(maze, False)
    # GPT.generate_log('2024_9')
    print('Sleep!')
