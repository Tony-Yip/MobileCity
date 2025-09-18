from datetime import datetime, timedelta
import json
import os
import re
import time

import aiohttp
import asyncio
import chromadb


class AgentMemory:
    def __init__(self, max_api):
        self.client = chromadb.Client()
        collections = self.client.list_collections()
        for collection in collections:
            self.client.delete_collection(collection.name)
        self.max_api_action = max_api
        self.max_api_conversation = max_api
        self.prompt_dir = 'prompt_templates/v3/'
        self.prompts_action_findings = []
        self.prompts_conversation = []

        self.dialogues = []
        self.dialogue_prompts = []

        with open ('maze/action_map.json', 'r') as json_file:
            action_map = json.load(json_file)
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

        with open('character/action_embeddings.json', 'r') as f:
            self.action_embeddings = json.load(f)


    async def call_chat_api_async(self, session, prompt):
        url = "your_chat_api_endpoint"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistralai-Ministral-8B-Instruct-2410",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        while True:
            try:
                async with session.post(url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    reply = result['choices'][0]['message']['content']
                    return reply
            except Exception as e:
                continue


    async def call_embedding_api_async(self, session, prompt):
        url = "your_embedding_api_endpoint"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "input": [prompt],
            "model": "maidalun1020-bce-embedding-base_v1"
        }
        
        try:
            async with session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                result = await response.json()
                return result
        except Exception as e:
            raise ValueError(e)


    def prompt_action_findings(self, task_description, task_place, persona_prompt):
        prompt_file = self.prompt_dir + '2_action_findings.txt'
        with open(prompt_file, 'r') as f:
            prompt_content = f.read()

        if task_place in self.action_map:
            task_place = self.action_map[task_place]
        elif task_place.split(':')[1][-6:-2] == 'Room':
            task_place = 'Home'

        replacements = {
            '0': persona_prompt,
            '1': task_description,
            '2': task_place.split(':')[-1]
        }
        
        prompt = self.replace_inputs(prompt_content, replacements)

        return prompt
    

    def prompt_conversation(self, characterA, characterB, memories_input, task_description, cur_time):
        prompt_file = self.prompt_dir + '3_3_dialogue_free.txt'
        with open(prompt_file, 'r') as f:
            prompt_content = f.read()

        task_place = characterA.task_place
        
        try:
            if task_place in self.action_map:
                task_place = self.action_map[task_place]
            elif task_place.split(':')[1][-6:-2] == 'Room':
                task_place = 'Home'
        except:
            task_place = 'Home'

        replacements = {
            '0': characterA.name,
            '1': characterB.name,
            '2': cur_time.strftime("%Y/%m/%d %H:%M"),
            '3': task_description,
            '4': task_place,
            '5': '\n'.join(memories_input['A_mem_action']),
            '6': '\n'.join(memories_input['A_mem_latest']),
            '7': '\n'.join(memories_input['AB_mem_action']),
            '8': '\n'.join(memories_input['B_mem_action']),
            '9': '\n'.join(memories_input['B_mem_latest']),
            '10': '\n'.join(memories_input['BA_mem_action']),
            '11': characterA.persona_prompt,
            '12': characterB.persona_prompt
        }
        
        prompt = self.replace_inputs(prompt_content, replacements)
        return prompt
    
    def prompt_dialogue_summary(self, characterA, characterB, dialogue, cur_time):

        prompt_file = self.prompt_dir + '3_2_summary.txt'
        with open(prompt_file, 'r') as f:
            prompt_content = f.read()

        replacements = {
            '0': characterA.name,
            '1': characterB.name,
            '2': cur_time.strftime("%Y/%m/%d %H:%M"),
            '3': dialogue,
            '4': characterA.task_description,
            '5': characterB.task_description,
            '6': characterA.persona_prompt,
            '7': characterB.persona_prompt            
        }

        prompt = self.replace_inputs(prompt_content, replacements)
        return prompt

    async def generate_action_memory(self, name, task_description, task_place, persona_prompt, cur_time):
        prompt = self.prompt_action_findings(task_description, task_place, persona_prompt)
        self.prompts_action_findings.append({
            'name': name,
            'prompt': prompt,
            'cur_time': cur_time
        })

        
        if len(self.prompts_action_findings) >= self.max_api_action:
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        api_calls = [
                            self.call_chat_api_async(session, task['prompt']) 
                            for task in self.prompts_action_findings
                        ]
                        text_results = await asyncio.gather(*api_calls)
                    async with aiohttp.ClientSession() as session:
                        api_calls = [
                            self.call_embedding_api_async(session, text_result)
                            for text_result in text_results
                        ]
                        embedding_results = await asyncio.gather(*api_calls)
                    break
                except:
                    time.sleep(1)
                    continue
            
            for idx in range(len(self.prompts_action_findings)):
                name = self.prompts_action_findings[idx]['name']
                memory = text_results[idx]
                embedding = embedding_results[idx]['data'][0]['embedding']
                cur_time = self.prompts_action_findings[idx]['cur_time']
                self.store_memory(f"{name}_self", memory, embedding, cur_time)
                
            self.prompts_action_findings = []


    async def generate_conversation_memory(self, characterA, characterB, cur_time, cur_place):

        self.prompts_conversation.append({
            'characterA': characterA,
            'characterB': characterB,
            'task_description': characterA.task_description,
            'cur_time': cur_time,
            'cur_place': cur_place,
            'embedding': self.action_embeddings[characterA.task_description]
        })

        n = len(self.prompts_conversation)

        if n >= self.max_api_conversation:
            for idx in range(n):
                characterA = self.prompts_conversation[idx]['characterA']
                characterB = self.prompts_conversation[idx]['characterB']
                task_description = self.prompts_conversation[idx]['task_description']
                cur_time = self.prompts_conversation[idx]['cur_time']
                query_embedding = self.prompts_conversation[idx]['embedding']

                A_mem_db = f"{characterA.persona['name']}_self"
                A_memories = self.search_memories(A_mem_db, query_embedding, 4)
                A_mem_action = A_memories['documents'][0]
                A_mem_embedding = [list(emb) for emb in A_memories['embeddings']]
                # A_mem_latest = self.get_latest_memories(A_mem_db, 2)['documents']
                A_mem_latest = []
                AB_mem_action = []

                self.prompts_conversation[idx]['A_mem_action'] = {
                    'documents': A_mem_action,
                    'embeddings': A_mem_embedding
                }

                """
                AB_mem_db = f"{characterA.persona['name']}_{characterB.persona['name']}"
                try:
                    self.client.get_collection(name=AB_mem_db)
                    AB_mem_action = self.search_memories(characterB.task_description, AB_mem_db, 1)['documents'][0]
                except:
                    self.create_index(AB_mem_db)                
                """

                B_mem_db = f"{characterB.persona['name']}_self"
                B_memories = self.search_memories(B_mem_db, query_embedding, 4)
                B_mem_action = B_memories['documents'][0]
                B_mem_embedding = [list(emb) for emb in B_memories['embeddings']]
                # B_mem_latest = self.get_latest_memories(B_mem_db, 2)['documents']
                B_mem_latest = []
                BA_mem_action = []

                self.prompts_conversation[idx]['B_mem_action'] = {
                    'documents': B_mem_action,
                    'embeddings': B_mem_embedding
                }                

                """
                BA_mem_db = f"{characterB.persona['name']}_{characterA.persona['name']}"
                try:
                    self.client.get_collection(name=BA_mem_db)
                    BA_mem_action = self.search_memories(characterA.task_description, BA_mem_db, 1)['documents'][0]
                except:
                    self.create_index(BA_mem_db)               
                """

                memories_input = {
                    'A_mem_action': A_mem_action, 'A_mem_latest': A_mem_latest, 'AB_mem_action': AB_mem_action,
                    'B_mem_action': B_mem_action, 'B_mem_latest': B_mem_latest, 'BA_mem_action': BA_mem_action
                }
                
                prompt = self.prompt_conversation(characterA, characterB, memories_input, task_description, cur_time)
                self.prompts_conversation[idx]['prompt'] = prompt

            # """
            async with aiohttp.ClientSession() as session:
                api_calls = [
                    self.call_chat_api_async(session, task['prompt']) 
                    for task in self.prompts_conversation
                ]
                dialogue_results = await asyncio.gather(*api_calls)           
            # """

            for idx in range(n):
                characterA = self.prompts_conversation[idx]['characterA']
                characterB = self.prompts_conversation[idx]['characterB']
                cur_time = self.prompts_conversation[idx]['cur_time']
                cur_place = self.prompts_conversation[idx]['cur_place']

                json_conversation = {
                    'characterA': characterA.name,
                    'characterB': characterB.name,
                    'start_time': cur_time.strftime("%Y/%m/%d %H:%M:%S"),
                    'end_time': (cur_time + timedelta(minutes=9, seconds=45)).strftime("%Y/%m/%d %H:%M:%S"),
                    'place': cur_place,
                    'chat': 'You are the best!'
                }
                self.dialogues.append(json_conversation)
    
    def create_index(self, memory_index):
        self.collection = self.client.create_collection(name=memory_index, embedding_function=None)
    
    def store_memory(self, memory_index, memory, embedding, cur_time):
        collection = self.client.get_collection(name=memory_index)
        collection.add(
            documents=[memory],
            embeddings=[embedding],
            ids=[str(collection.count())],
            metadatas=[{'time': cur_time.strftime("%Y/%m/%d %H:%M:%S")}]
        )
        
    def search_memories(self, memory_index: str, query_embedding, k: int):
        collection = self.client.get_collection(name=memory_index)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["embeddings", "documents"]
        )
        return results
    
    def get_latest_memories(self, memory_index: str, k: int):
        collection = self.client.get_collection(name=memory_index)
        total_count = collection.count()
        skip_count = max(0, total_count - k)
        
        return collection.get(limit=k, offset=skip_count)
    
    def save_to_cache(self, cache_path):
        collections = self.client.list_collections()
        cache_data = {}
        
        for collection_info in collections:
            collection_name = collection_info.name
            collection = self.client.get_collection(name=collection_name)
            all_data = collection.get()
            cache_data[collection_name] = {
                'documents': all_data['documents'],
                'embeddings': all_data['embeddings'],
                'ids': all_data['ids'],
                'metadatas': all_data['metadatas']
            }
        
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)

    def load_from_cache(self, cache_path):
        """Load all memory indexes/collections from cache file"""
        if not os.path.exists(cache_path):
            return False
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)

        """
        for memory_index, data in cache_data.items():
            collection = self.client.create_collection(name=memory_index)
            if data['documents']:
                collection.add(
                    documents=data['documents'],
                    embeddings=data['embeddings'],
                    ids=data['ids'],
                    metadatas=data['metadatas']
                )        
        """

        idx = 0
        for memory_index, data in cache_data.items():
            collection = self.client.create_collection(name=memory_index)
            if data['documents']:
                embeddings = []
                for i, doc in enumerate(data['documents']):
                    embedding = self.get_embedding(doc)
                    embeddings.append(embedding)
                collection.add(
                    documents=data['documents'],
                    embeddings=embeddings,
                    ids=data['ids'],
                    metadatas=data['metadatas']
                )
            idx += 1
            print(f"\r{idx}/{len(cache_data)}", end="", flush=True)

    def replace_inputs(self, prompt_content, replacements):
        return re.sub(r'!<INPUT\s+(\d+)>!', 
                    lambda m: replacements.get(m.group(1), m.group(0)), 
                    prompt_content)

    async def finish_everything(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    api_calls = [
                        self.call_chat_api_async(session, task['prompt']) 
                        for task in self.prompts_action_findings
                    ]
                    text_results = await asyncio.gather(*api_calls)
                async with aiohttp.ClientSession() as session:
                    api_calls = [
                        self.call_embedding_api_async(session, text_result)
                        for text_result in text_results
                    ]
                    embedding_results = await asyncio.gather(*api_calls)
                break
            except:
                time.sleep(1)
                continue
        
        for idx in range(len(self.prompts_action_findings)):
            name = self.prompts_action_findings[idx]['name']
            memory = text_results[idx]
            embedding = embedding_results[idx]['data'][0]['embedding']
            cur_time = self.prompts_action_findings[idx]['cur_time']
            self.store_memory(f"{name}_self", memory, embedding, cur_time)
            
        self.prompts_action_findings = []


        n = len(self.prompts_conversation)
        for idx in range(n):
            characterA = self.prompts_conversation[idx]['characterA']
            characterB = self.prompts_conversation[idx]['characterB']
            task_description = self.prompts_conversation[idx]['task_description']
            cur_time = self.prompts_conversation[idx]['cur_time']
            query_embedding = self.prompts_conversation[idx]['embedding']

            A_mem_db = f"{characterA.persona['name']}_self"
            A_memories = self.search_memories(A_mem_db, query_embedding, 4)
            A_mem_action = A_memories['documents'][0]
            A_mem_embedding = [list(emb) for emb in A_memories['embeddings']]
            # A_mem_latest = self.get_latest_memories(A_mem_db, 2)['documents']
            A_mem_latest = []
            AB_mem_action = []

            self.prompts_conversation[idx]['A_mem_action'] = {
                'documents': A_mem_action,
                'embeddings': A_mem_embedding
            }

            B_mem_db = f"{characterB.persona['name']}_self"
            B_memories = self.search_memories(B_mem_db, query_embedding, 4)
            B_mem_action = B_memories['documents'][0]
            B_mem_embedding = [list(emb) for emb in B_memories['embeddings']]
            # B_mem_latest = self.get_latest_memories(B_mem_db, 2)['documents']
            B_mem_latest = []
            BA_mem_action = []

            self.prompts_conversation[idx]['B_mem_action'] = {
                'documents': B_mem_action,
                'embeddings': B_mem_embedding
            }                

            memories_input = {
                'A_mem_action': A_mem_action, 'A_mem_latest': A_mem_latest, 'AB_mem_action': AB_mem_action,
                'B_mem_action': B_mem_action, 'B_mem_latest': B_mem_latest, 'BA_mem_action': BA_mem_action
            }
            
            prompt = self.prompt_conversation(characterA, characterB, memories_input, task_description, cur_time)
            self.prompts_conversation[idx]['prompt'] = prompt


        while True:
            async with aiohttp.ClientSession() as session:
                api_calls = [
                    self.call_chat_api_async(session, task['prompt']) 
                    for task in self.prompts_conversation
                ]
                dialogue_results = await asyncio.gather(*api_calls)
                # dialogue_results = [dialogue_result.split('\n') for dialogue_result in dialogue_results]

            try:

                async with aiohttp.ClientSession() as session:
                    api_calls = [
                        self.call_embedding_api_async(session, dialogue_result)
                        for dialogue_result in dialogue_results
                    ]
                    embedding_results_B = await asyncio.gather(*api_calls)
                embedding_results_A = embedding_results_B
                break

            except:
                continue


        for idx in range(n):
            characterA = self.prompts_conversation[idx]['characterA']
            characterB = self.prompts_conversation[idx]['characterB']
            cur_time = self.prompts_conversation[idx]['cur_time']
            cur_place = self.prompts_conversation[idx]['cur_place']

            json_conversation = {
                'characterA': characterA.name,
                'characterB': characterB.name,
                'start_time': cur_time.strftime("%Y/%m/%d %H:%M:%S"),
                'end_time': (cur_time + timedelta(minutes=9, seconds=45)).strftime("%Y/%m/%d %H:%M:%S"),
                'place': cur_place,
                'chat': dialogue_results[idx]
            }
            self.dialogues.append(json_conversation)

            self.store_memory(f"{characterB.name}_self", dialogue_results[idx][1], embedding_results_B[idx]['data'][0]['embedding'], cur_time)
            for memory_idx in range(len(self.prompts_conversation[idx]['A_mem_action']['documents'])):
                memory = f"{characterA.name} told me: {self.prompts_conversation[idx]['A_mem_action']['documents'][memory_idx]}"
                embedding = self.prompts_conversation[idx]['A_mem_action']['embeddings'][0][memory_idx]
                self.store_memory(f"{characterB.name}_self", memory, embedding, cur_time)

            self.store_memory(f"{characterA.name}_self", dialogue_results[idx][0], embedding_results_A[idx]['data'][0]['embedding'], cur_time)
            for memory_idx in range(len(self.prompts_conversation[idx]['B_mem_action']['documents'])):
                memory = f"{characterB.name} told me: {self.prompts_conversation[idx]['B_mem_action']['documents'][memory_idx]}"
                embedding = self.prompts_conversation[idx]['B_mem_action']['embeddings'][0][memory_idx]
                self.store_memory(f"{characterA.name}_self", memory, embedding, cur_time)
 

        with open(f"{self.output_folder}/dialogue.jsonl", "w") as outfile:
            for json_conversation in self.dialogues:
                json_line = json.dumps(json_conversation, ensure_ascii=False)
                outfile.write(json_line + '\n')