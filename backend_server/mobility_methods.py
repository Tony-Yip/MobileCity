
import csv

def refresh_mobility(fake_mobility):
    if fake_mobility==-1: return -1
    type_list = []
    flag = False

    for place in fake_mobility[0]:
        if place[-5:-2] == 'PMV' or place[-5:-2] == 'Bus':
            flag = not flag
            if flag:
                if place[-5:-2] == 'PMV':
                    type_list.append(1)
                else:
                    type_list.append(2)
        if not flag:
            type_list.append(0)
    
    mobility = {
        'type': type_list, 'path': fake_mobility[0], 'time_cost': fake_mobility[1]
    }
    return mobility

def create_PMV_route():
    PMV_route = [[(30, 9), (9, 9)],
                [(70, 29), (9, 29)],
                [(70, 49), (9, 49)],
                [(70, 69), (9, 69)],
                [(70, 89), (9, 89)],
                [(9, 10), (30, 10)],
                [(9, 30), (70, 30)],
                [(9, 50), (70, 50)],
                [(9, 70), (70, 70)],
                [(9, 90), (70, 90)],
                [(10, 90), (10, 9)],
                [(30, 90), (30, 9)],
                [(50, 90), (50, 29)],
                [(70, 90), (70, 29)],
                [(9, 9), (9, 90)],
                [(29, 9), (29, 90)],
                [(49, 29), (49, 90)],
                [(69, 29), (69, 90)]]
    
    def transfer_route(route):

        cur_station = route[0]
        nxt_station = route[1]
        
        if cur_station[0] == nxt_station[0]:
            if cur_station[1] < nxt_station[1]:
                new_nodes = [(cur_station[0], x) for x in range(cur_station[1], nxt_station[1])]
            else:
                new_nodes = [(cur_station[0], x) for x in range(cur_station[1], nxt_station[1], -1)]
        elif cur_station[1] == nxt_station[1]:
            if cur_station[0] < nxt_station[0]:
                new_nodes = [(y, cur_station[1]) for y in range(cur_station[0], nxt_station[0])]
            else:
                new_nodes = [(y, cur_station[1]) for y in range(cur_station[0], nxt_station[0], -1)]   
        else:
            raise ValueError('Not valid stations!')
        new_nodes.append(nxt_station)
        
        return new_nodes

    with open('PMV_route.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        for route in PMV_route:
            writer.writerow(transfer_route(route))



def create_bus_route():
  route_clockwise = [(29, 13), (29, 106), (30, 106), (30, 90), (70, 90), (70, 29), (30, 29), (30, 13), (29, 13)]
  route_counterclockwise = [(30, 89), (30, 30), (69, 30), (69, 89), (30, 89)]

  def transfer_route(route):
      nodes = []
      for i in range(len(route)-1):
          cur_station = route[i]
          nxt_station = route[i+1]
          
          if cur_station[0] == nxt_station[0]:
              if cur_station[1] < nxt_station[1]:
                  new_nodes = [(cur_station[0], x) for x in range(cur_station[1], nxt_station[1])]
              else:
                  new_nodes = [(cur_station[0], x) for x in range(cur_station[1], nxt_station[1], -1)]
          elif cur_station[1] == nxt_station[1]:
              if cur_station[0] < nxt_station[0]:
                  new_nodes = [(y, cur_station[1]) for y in range(cur_station[0], nxt_station[0])]
              else:
                  new_nodes = [(y, cur_station[1]) for y in range(cur_station[0], nxt_station[0], -1)]   
          else:
              raise ValueError('Not valid stations!')
          nodes += new_nodes
      nodes.append(route[-1])    
      return nodes

  route_clockwise = route_clockwise[::-1]
  with open('Bus_route.csv', 'w', newline='') as file:
      writer = csv.writer(file)
      writer.writerow(transfer_route(route_clockwise))
      writer.writerow(transfer_route(route_counterclockwise))

def refresh_mobility_fake(mobility):
  if mobility == -1: return -1
  if mobility['transportation'] == 0:
    mobility['type'] = [0]*(len(mobility['path']))
  elif mobility['transportation'] == 1:
    type_list = []
    path_list = []
    flag = False
    for place in mobility['path']:
      if place[-5:-2] == 'PMV':
        flag = not flag
        if flag:
          type_list.append(1)
          path_list.append(place)
      if not flag:
        type_list.append(0)
        path_list.append(place)
    mobility['type'] = type_list
    mobility['path'] = path_list
  else:
    type_list = []
    path_list = []
    flag = False
    for place in mobility['path']:
      if not flag:
        if place[-5:-2] == 'Bus':
          flag = True
          type_list.append(2)
          path_list.append(place)          
        else:
          type_list.append(0)
          path_list.append(place)
      else:
        if flag:
          if place[-5:-2] == 'Bus':
            last_place = place
          else:
            flag = False
            type_list.append(0)
            path_list.append(last_place)
            path_list.append(place)
    type_list.append(0)

    mobility['type'] = type_list
    mobility['path'] = path_list     


  return mobility

def search_closet_highway(maze, x, y):
  assert maze.find_tile_attribute(x, y)['sector'] != 'Highway'
  if maze.find_tile_attribute(x+1, y)['sector'] == 'Highway':
    return [x+1, y]
  elif maze.find_tile_attribute(x-1, y)['sector'] == 'Highway':
    return [x-1, y]
  elif maze.find_tile_attribute(x, y+1)['sector'] == 'Highway':
    return [x, y+1]
  elif maze.find_tile_attribute(x, y-1)['sector'] == 'Highway':
    return [x, y-1]
  else:
    raise ValueError('No highway tile is found!')
  # Crossing x Crossing Y

def search_closet_walkway(maze, x, y):
  assert maze.find_tile_attribute(x, y)['sector'] == 'Highway'
  if maze.find_tile_attribute(x+1, y)['sector'] != 'Highway':
    return [x+1, y]
  elif maze.find_tile_attribute(x-1, y)['sector'] != 'Highway':
    return [x-1, y]
  elif maze.find_tile_attribute(x, y+1)['sector'] != 'Highway':
    return [x, y+1]
  elif maze.find_tile_attribute(x, y-1)['sector'] != 'Highway':
    return [x, y-1]
  else:
    raise ValueError('No walkway tile is found!')
  

if __name__ == '__main__':
  mobility_list = \
  [-1,
  {'transportation': 1,
    'start_time': '08:49:00',
    'end_time': '09:00:00',
    'path': ['Apartment B:Room C',
    'Apartment B:PMV:1',
    'Central Crossing 2',
    'Central Crossing 3',
    'Company B:PMV:0',
    'Company B:Office D']},
  {'transportation': 0,
    'start_time': '11:58:30',
    'end_time': '12:00:00',
    'path': ['Company B:Office D', 'Company B:Company Canteen']},
  {'transportation': 0,
    'start_time': '12:45:00',
    'end_time': '12:46:30',
    'path': ['Company B:Company Canteen', 'Company B:Office D']},
  {'transportation': 0,
    'start_time': '18:00:00',
    'end_time': '18:20:45',
    'path': ['Company B:Office D',
    'Company B:Crossing:1',
    'Apartment C:Crossing:3',
    'Apartment C:Crossing:2',
    'Apartment B:Crossing:3',
    'Apartment B:Restaurant']},
  {'transportation': 0,
    'start_time': '19:54:00',
    'end_time': '20:00:00',
    'path': ['Apartment B:Restaurant', 'Apartment B:Room C']},
  -1]

  x = refresh_mobility(mobility_list[1])
  print('------')