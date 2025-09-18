import json
import os

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

def home(request):
    
    simcode = os.environ.get('SIMCODE', 'default_value')

    persona_names = []
    persona_tiles = []

    file_path = f"storage/{simcode}/0.json"
    with open(file_path, 'r', encoding='utf-8') as name2tile_file:
      name2tile = json.load(name2tile_file)
      for name, tile in name2tile.items():
        if len(name.split())>1:
          persona_name = [name, name.split()[0][0]+name.split()[1][0]]
        else:
          persona_name = [name, name]
        persona_tile = [name, tile['x'], tile['y']]
        persona_names.append(persona_name)
        persona_tiles.append(persona_tile)
    
    context = {
            "sim_code": simcode,
            "step": 0, 
            "persona_names": persona_names,
            "persona_init_pos": persona_tiles,
            "mode": "simulate"}
    template = "home/home.html"
    return render(request, template, context)

@csrf_exempt
def process_environment(request): 
  """
  <FRONTEND to BACKEND> 
  This sends the frontend visual world information to the backend server. 
  It does this by writing the current environment representation to 
  "storage/environment.json" file. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]
  environment = data["environment"]

  with open(f"storage/{sim_code}/environment/{step}.json", "w") as outfile:
    outfile.write(json.dumps(environment, indent=2))

  return HttpResponse("received")

@csrf_exempt
def update_environment(request):
  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]

  response_data = {"<step>": -1}
  try:
    with open(f"storage/{sim_code}/movement/{step}.json") as json_file: 
      response_data = json.load(json_file)
      response_data["<step>"] = step
  except:
    pass

  return JsonResponse(response_data)