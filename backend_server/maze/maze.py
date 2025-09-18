import ast
import math

import networkx as nx

from global_methods import *
from mobility_methods import *

class Maze:
    def __init__(self, maze_name):
        self.maze_name = maze_name
        env_matrix = '../frontend_server/static_dirs/assets/city/matrix'
        self.maze_folder = f"{env_matrix}/maze"
        self.blocks_folder = f"{env_matrix}/special_blocks"

        sb_dict = self.load_blocks("/sector_blocks.csv")
        ab_dict = self.load_blocks("/arena_blocks.csv")
        rb_dict = self.load_blocks("/road_blocks.csv")
        lb_dict = self.load_blocks("/location_blocks.csv")

        collision_maze_raw = self.load_maze("/walls_maze.csv")
        sector_maze_raw = self.load_maze("/sector_maze.csv")
        arena_maze_raw = self.load_maze("/arena_maze.csv")
        road_maze_raw = self.load_maze("/road_maze.csv")
        location_maze_raw = self.load_maze("/location_maze.csv")
        
        for i in range(len(collision_maze_raw)):
            for j in range(len(collision_maze_raw[0])):
                if collision_maze_raw[i][j] == '-1':
                    collision_maze_raw[i][j] = 0
                else:
                    collision_maze_raw[i][j] = 1

        self.tiles = []
        self.submap = {sector: {
            'boarder': {'left_up': [], 'right_down': []},
            'Crossing': [],
            'Arena': {},
            'PMV Station': [],
            'Bus Station': []
        } for sector in sb_dict.values()}
        self.road_crossing = {}
        # arena -> tiles
        self.arena_tiles = {}
        self.arena_tiles['PMV Station'] = []
        self.arena_tiles['Bus Station'] = []
        for i in range(len(sector_maze_raw)):
            tile_rows = []
            for j in range(len(sector_maze_raw[0])):
                tile_details = dict()
                collision = False if collision_maze_raw[i][j] == 0 else True
                tile_details['collision'] = collision
                sector_key = sector_maze_raw[i][j]
                if sector_key != '-1':
                    sector = sb_dict[sector_key]
                    tile_details['sector'] = sector
                    if self.submap[sector]['boarder']['left_up'] == []:
                        self.submap[sector]['boarder']['left_up'] = [i, j]
                    if self.submap[sector]['boarder']['right_down'] == []:
                        self.submap[sector]['boarder']['right_down'] = [i, j]
                    else:
                        cur_i = self.submap[sector]['boarder']['right_down'][0]
                        cur_j = self.submap[sector]['boarder']['right_down'][1]
                        self.submap[sector]['boarder']['right_down'] = \
                            [max(i,cur_i), max(j,cur_j)]
                    if sector_key != '1' and not collision:
                        arena_key = arena_maze_raw[i][j]
                        location_key = location_maze_raw[i][j]
                        if arena_key != '-1':
                            arena = ab_dict[arena_key]
                            tile_details['arena'] = arena
                            # find the location of this arena
                            if location_key != '-1':
                                if arena not in self.submap[sector]['Arena'].keys():
                                    self.submap[sector]['Arena'][arena] = [(i,j)]
                                else:
                                    self.submap[sector]['Arena'][arena].append((i,j))
                            else:
                                self.arena_tiles[f"{sector}:{arena}"] = \
                                    self.arena_tiles.get(f"{sector}:{arena}", [])+[(i,j)]
                        else:
                            if location_key != '-1':
                                location = lb_dict[location_key]
                                self.submap[sector][location].append((i,j))
                                tile_details['location'] = location
                                if location_key == '15':
                                    self.arena_tiles['PMV Station'].append((i,j))
                                elif location_key == '14':
                                    self.arena_tiles['Bus Station'].append((i,j))
                
                else:
                    road_key = road_maze_raw[i][j]
                    if road_key != '-1':
                        tile_details['sector'] = rb_dict[road_key]
                        if road_key != '80':
                            self.road_crossing[(i,j)] = True
                        # if road_maze_raw[i][j-1] != '-1':
                        #     self.PMV_road_graph.add_edge((i,j), (i,j-1))
                        # if road_maze_raw[i-1][j] != '-1':
                        #     self.PMV_road_graph.add_edge((i,j), (i-1,j))
                tile_rows.append(tile_details)
            self.tiles.append(tile_rows)

        self.arena_characters = {key:set() for key in self.arena_tiles if not key.endswith('Station') and not key.endswith('Passage')}
        self.location_dict = {}
        self.sector_crossing_dict = {}
        for sector in self.submap.keys():
            left_up = self.submap[sector]['boarder']['left_up']
            right_down = self.submap[sector]['boarder']['right_down']
            submaze = []
            for i in range(left_up[0], right_down[0]+1):
                submaze.append(collision_maze_raw[i][left_up[1]: right_down[1]+1])
            self.submap[sector]['submaze'] = submaze
            self.submap[sector]['nx_fake'], self.submap[sector]['nx'] = self.create_subgraph(sector)

        self.walking_graph, self.PMV_graph, self.bus_graph, self.PMV_road_graph, self.bus_road_graph = self.create_graph()
        

    def create_graph(self):

        walking_graph = nx.DiGraph()

        for sector in self.submap.keys():
            walking_graph = nx.compose(walking_graph, self.submap[sector]['nx'])

        # add walking edges
        for cd in self.sector_crossing_dict.keys():
            if self.sector_crossing_dict[cd]['connected'] == False:
                node_i = self.sector_crossing_dict[cd]['node']
                if (cd[0], cd[1]+3) in self.sector_crossing_dict.keys():
                    self.sector_crossing_dict[(cd[0], cd[1]+3)]['connected'] == True
                    node_j = self.sector_crossing_dict[(cd[0], cd[1]+3)]['node']
                elif (cd[0], cd[1]-3) in self.sector_crossing_dict.keys():
                    self.sector_crossing_dict[(cd[0], cd[1]-3)]['connected'] == True
                    node_j = self.sector_crossing_dict[(cd[0], cd[1]-3)]['node']
                elif (cd[0]+3, cd[1]) in self.sector_crossing_dict.keys():
                    self.sector_crossing_dict[(cd[0]+3, cd[1])]['connected'] == True
                    node_j = self.sector_crossing_dict[(cd[0]+3, cd[1])]['node']
                elif (cd[0]-3, cd[1]) in self.sector_crossing_dict.keys():
                    self.sector_crossing_dict[(cd[0]-3, cd[1])]['connected'] == True
                    node_j = self.sector_crossing_dict[(cd[0]-3, cd[1])]['node']
                else:
                    raise ValueError(f"No crossing pair for {cd} is found!")  
                self.sector_crossing_dict[cd]['connected'] == True
                walking_graph.add_edge(node_i, node_j, edge_type='walking', time_cost=3, money_cost=0)
        
        """
        # add PMV edges
        PMV_csv_file = stations_dir+'/PMV_station.csv'
        rows = read_file_to_list(PMV_csv_file, header=False)
        for row in rows:
            time_cost = float(row[2])
            money_cost = max(time_cost*25, 25)
            PMV_graph.add_edge(row[0], row[1], edge_type='PMV', time_cost=time_cost, money_cost=money_cost)

        # add bus edges
        Bus_csv_file = stations_dir+'/Bus_station.csv'
        rows = read_file_to_list(Bus_csv_file, header=False)
        for row in rows:
            time_cost = float(row[2])
            money_cost = time_cost*100
            bus_graph.add_edge(row[0], row[1], edge_type='bus', time_cost=time_cost, money_cost=money_cost)
        """

        stations_dir = '../frontend_server/static_dirs/assets/city/matrix/stations'
        
        # add bus stations
        bus_road_graph = nx.DiGraph()
        Bus_route_csv_file = stations_dir+'/Bus_route.csv'
        with open(Bus_route_csv_file, 'r', newline='') as file:
            reader = csv.reader(file)
            for stations in reader:
                for index in range(len(stations)-1):
                    cur_station = stations[index]
                    nxt_station = stations[index+1]
                    cur_station = ast.literal_eval(cur_station)
                    nxt_station = ast.literal_eval(nxt_station)
                    bus_road_graph.add_edge(cur_station, nxt_station, distance=1)

        # add PMV stations
        PMV_road_graph = nx.DiGraph()
        PMV_route_csv_file = stations_dir+'/PMV_route.csv'
        with open(PMV_route_csv_file, 'r', newline='') as file:
            reader = csv.reader(file)
            for stations in reader:
                for index in range(len(stations)-1):
                    cur_station = stations[index]
                    nxt_station = stations[index+1]
                    cur_station = ast.literal_eval(cur_station)
                    nxt_station = ast.literal_eval(nxt_station)
                    PMV_road_graph.add_edge(cur_station, nxt_station, distance=1)

        PMV_keys, bus_keys = [], []
        for key in self.location_dict.keys():
            key_split = key.split(':')[1]
            if key_split=='PMV': PMV_keys.append(key)
            elif key_split=='Bus': bus_keys.append(key)
        PMV_station_dict, bus_station_dict = {}, {}

        # create PMV graph
        PMV_graph = walking_graph.copy()
        for PMV_key in PMV_keys:
            PMV_walkway_tile_tuple = self.location_dict[PMV_key]
            PMV_highway_tile = search_closet_highway(self, PMV_walkway_tile_tuple[1], PMV_walkway_tile_tuple[0])
            PMV_highway_tile_tuple = (PMV_highway_tile[1], PMV_highway_tile[0])
            PMV_station_dict[PMV_key] = PMV_highway_tile_tuple
        for i in range(len(PMV_keys)):
            PMV_start_tile = PMV_station_dict[PMV_keys[i]]
            for j in range(len(PMV_keys)):
                if i==j: continue
                PMV_end_tile = PMV_station_dict[PMV_keys[j]]
                path_distance, _ = nx.bidirectional_dijkstra(PMV_road_graph, source=PMV_start_tile, target=PMV_end_tile)
                time_cost = math.ceil(path_distance/2)
                # time: 10-61 money in data: 0.4-3.2
                money_cost = round(time_cost*0.05, 2)
                PMV_graph.add_edge(PMV_keys[i], PMV_keys[j], edge_type='PMV', time_cost=time_cost, money_cost=money_cost)
        
        # create bus graph
        bus_graph = walking_graph.copy() 
        for bus_key in bus_keys:
            bus_walkway_tile_tuple = self.location_dict[bus_key]
            bus_highway_tile = search_closet_highway(self, bus_walkway_tile_tuple[1], bus_walkway_tile_tuple[0])
            bus_highway_tile_tuple = (bus_highway_tile[1], bus_highway_tile[0])
            bus_station_dict[bus_key] = bus_highway_tile_tuple
        for i in range(len(bus_keys)-1):
            bus_start_tile = bus_station_dict[bus_keys[i]]
            for j in range(i, len(bus_keys)):
                if i==j: continue
                bus_end_tile = bus_station_dict[bus_keys[j]]
                try:
                    path_distance, _ = nx.bidirectional_dijkstra(bus_road_graph, source=bus_start_tile, target=bus_end_tile)
                except:
                    continue
                time_cost = math.ceil(path_distance/5)      
                # time: 4-35 money in data: 1.6-2.4
                money_cost = 1.50 + round(time_cost*0.025, 2)
                bus_graph.add_edge(bus_keys[i], bus_keys[j], edge_type='bus', time_cost=time_cost, money_cost=money_cost)
 
        return walking_graph, PMV_graph, bus_graph, PMV_road_graph, bus_road_graph

    def create_subgraph(self, sector):
        submaze = self.submap[sector]['submaze']
        left_up = self.submap[sector]['boarder']['left_up']

        fake_graph = nx.Graph()
        for i in range(len(submaze)):
            for j in range(len(submaze[0])):
                if submaze[i][j]==0:
                    new_i, new_j = i+left_up[0], j+left_up[1]
                    if j<len(submaze[0])-1 and submaze[i][j+1]==0:
                        fake_graph.add_edge((new_i,new_j), (new_i,new_j+1), edge_type='walking', time_cost=1, money_cost=0)
                    if i<len(submaze)-1 and submaze[i+1][j]==0:
                        fake_graph.add_edge((new_i,new_j), (new_i+1,new_j), edge_type='walking', time_cost=1, money_cost=0)

        temp_arena = self.submap[sector]['Arena']

        PMV_station_list = self.submap[sector]['PMV Station']
        Bus_station_list = self.submap[sector]['Bus Station']
        crossing_list = self.submap[sector]['Crossing']
        
        for i in range(len(PMV_station_list)):
            temp_arena[f"PMV:{i}"] = [PMV_station_list[i]]
        for i in range(len(Bus_station_list)):
            temp_arena[f"Bus:{i}"] = [Bus_station_list[i]]
        for i in range(len(crossing_list)):
            temp_arena[f"Crossing:{i}"] = [crossing_list[i]]
            self.sector_crossing_dict[tuple(crossing_list[i])] = \
                {'node': f"{sector}:Crossing:{i}", 'connected': False}

        real_graph = nx.DiGraph()
        arena_keys = list(temp_arena.keys())
        del_keys = []
        extended_arena = {}
        for key, coordinates in temp_arena.items():
            if len(coordinates)>1: 
                del_keys.append(key)
                for i in range(len(coordinates)):
                    coordinate = coordinates[i]
                    # coordinate = [coordinate[0]-left_up[0], coordinate[1]-left_up[1]]
                    extended_arena[f"{key}:{i}"] = coordinate
            else:
                # coordinate = [coordinates[0][0]-left_up[0], coordinates[0][1]-left_up[1]]
                temp_arena[key] = coordinates[0]
            
        for key in del_keys:
            del temp_arena[key]
        for key, coordinate in extended_arena.items():
            temp_arena[key] = coordinate

        arena_keys = list(temp_arena.keys())
        for i in range(len(arena_keys)):
            self.location_dict[f"{sector}:{arena_keys[i]}"] = tuple(temp_arena[arena_keys[i]])
            for j in range(i+1, len(arena_keys)):
                coordinate_i = temp_arena[arena_keys[i]]
                coordinate_j = temp_arena[arena_keys[j]]
                distance = nx.shortest_path_length(fake_graph, source=tuple(coordinate_i), target=tuple(coordinate_j), weight='time_cost')
                real_graph.add_edge(f"{sector}:{arena_keys[i]}", f"{sector}:{arena_keys[j]}", edge_type='walking', time_cost=distance, money_cost=0)
                real_graph.add_edge(f"{sector}:{arena_keys[j]}", f"{sector}:{arena_keys[i]}", edge_type='walking', time_cost=distance, money_cost=0)

        return fake_graph, real_graph

    def load_blocks(self, csv_file):
        csv_file = self.blocks_folder + csv_file
        rows = read_file_to_list(csv_file, header=False)
        csv_dict = dict()
        for i in rows: csv_dict[i[0]] = i[-1]
        return csv_dict
    
    def load_maze(self, csv_file):
        csv_file = self.maze_folder + csv_file
        maze = read_file_to_list(csv_file, header=False)
        return maze

    def find_tile_attribute(self, x, y):
        tile_info = self.tiles[y][x]
        keys = ['collision', 'sector', 'arena', 'location']
        for key in keys:
            if key not in tile_info:
                tile_info[key] = -1
        return tile_info

    def get_fastest_path(self, source, target):


        walking_path_time, walking_path = nx.bidirectional_dijkstra(self.walking_graph, source=source, target=target, weight='time_cost')
        # walking_path = nx.shortest_path(self.walking_graph, source=source, target=target, weight='time_cost')        
        walking_path_time = round(walking_path_time, 2)

        PMV_path_time, PMV_path = nx.bidirectional_dijkstra(self.PMV_graph, source=source, target=target, weight='time_cost')
        PMV_path_time = round(PMV_path_time, 2)
        PMV_walking_time_cost, PMV_onboard_time_cost, PMV_money = \
            calculate_time_money_cost(self.PMV_graph, PMV_path)
        if PMV_path_time >= walking_path_time:
            PMV_path, PMV_walking_time_cost, PMV_onboard_time_cost, PMV_money = -1, float('inf'), float('inf'), float('inf')
        PMV_walking_time_cost = round(PMV_walking_time_cost, 2)
        
        bus_path_time, bus_path = nx.bidirectional_dijkstra(self.bus_graph, source=source, target=target, weight='time_cost')
        bus_path_time = round(bus_path_time, 2)
        bus_walking_time_cost, bus_onboard_time_cost, bus_money = \
            calculate_time_money_cost(self.bus_graph, bus_path)
        if bus_path_time >= walking_path_time:
            bus_path, bus_walking_time_cost, bus_onboard_time_cost, bus_money = -1, float('inf'), float('inf'), float('inf')   
        bus_walking_time_cost = round(bus_walking_time_cost, 2)

        paths = [walking_path, PMV_path, bus_path]
        time_costs = [walking_path_time, PMV_path_time, bus_path_time]
        walking_time_costs = [walking_path_time, PMV_walking_time_cost, bus_walking_time_cost]
        onboard_time_costs = [0, PMV_onboard_time_cost, bus_onboard_time_cost]
        money_costs = [0, PMV_money, bus_money]


        return paths, time_costs, walking_time_costs, onboard_time_costs, money_costs

if __name__ == '__main__':
    maze = Maze('City')
    x = maze.get_fastest_path('Company A:Office B', 'Apartment H:Room C')
    print('--------------------')
    # _, path = nx.bidirectional_dijkstra(maze.submap[sector]['nx_fake'], source=target, target=source, weight='time_cost')
