import json
import math
import random
import requests

class Centroid:
    def __init__(self, x, y, t_func, ph_func):
        self.x = x
        self.y = y
        self.t_func = t_func
        self.ph_func = ph_func

if __name__ == '__main__':
    start_x = 0
    start_y = 0

    curr_x = start_x 
    curr_y = start_y 

    inner_radius = 1000 
    outer_radius = 4000 

    num_planets = 25 
    planets_per_sector = 4

    starting_num = 1000


    def tmp_function(x, y, c_x, c_y):
        d_x = math.fabs(c_x - x)
        d_y = math.fabs(c_y - y)

        t_range = d_x / inner_radius
        t_start = 1 - (d_y / inner_radius) 

        return (t_start, t_start + t_range)

    sector_centroids = []
    num_sectors = max(1, num_planets / planets_per_sector)
    for i in range(num_sectors):
        sector_centroids.append(Centroid(curr_x, curr_y, tmp_function, tmp_function))

        angle = random.random() * (3.14159 / 2)

        curr_x += int(math.cos(angle)*outer_radius)
        curr_y += int(math.sin(angle)*outer_radius)

    for i in range(num_planets):
        centroid = sector_centroids[min(len(sector_centroids)-1, int(i / planets_per_sector))]
        json_blob = {}

        x_offset = random.random() * 2 * inner_radius - inner_radius
        y_offset = random.random() * 2 * inner_radius - inner_radius

        x = centroid.x + x_offset
        y = centroid.y + y_offset

        pid = starting_num + i
        json_blob['PlanetId'] = pid
        json_blob['PlanetName'] = 'Planet %s'%pid
        json_blob['SpacePosition'] = { 'x': x, 'y': y }
        temp = centroid.t_func(x, y, centroid.x, centroid.y);
        json_blob['Temperature'] =  { 'Min': temp[0], 'Max': temp[1] }
        ph = centroid.ph_func(x, y, centroid.x, centroid.y)
        json_blob['Ph'] =  { 'Min': ph[0], 'Max': ph[1] }

        db_url = 'http://localhost:8081/persistence/planets/%i'%pid
        print json_blob
        print requests.post(db_url, json=json_blob)
