import json
import math
import random
import requests



class NameGenerator:

    def __init__(self):
        self.name_list = [] 


    def populate_namelist(self): 
        import xmlrpclib

        proxy = xmlrpclib.ServerProxy("https://dicelog.com/yaf/rpc")

        long_min = 4
        long_max = 8
        quantity = 10

        result = proxy.names(long_min, long_max, quantity)

        self.name_list.extend(result.split('\n'))


    def get_name(self):
        if len(self.name_list) == 0:
            self.populate_namelist()

        return self.name_list.pop(0)


class Centroid:
    def __init__(self, x, y, t_func, ph_func):
        self.x = x
        self.y = y
        self.t_func = t_func
        self.ph_func = ph_func

        # Tons of magic numbers here some of this shares Polyminis data
        # so maybe it should live in the DB? (TODO)

        #  Temperature uses a fairly normal distribution ( avg = [0.25, 0.75], 0.25 - 0.75 range)
        #[0.25, 0.75]
        temp_average = random.random() * 0.5 + 0.25
        #[0.25, 0.5]
        temp_band_size =  ( random.random() * 0.25 + 0.25 ) / 2.0

        self.base_temp = temp_average - temp_band_size
        self.base_max_temp = temp_average + temp_band_size

        # For PH we want more volatility so it's a bigger band ( avg = [0.4, 0.6], 0 - 1 range)
        #[0.4, 0.6]
        ph_average = random.random() * 0.2 + 0.4
        #[0.2, 0.8]
        ph_band_size = ( random.random() * 0.6 + 0.2 ) / 2.0
        self.base_ph = ph_average - ph_band_size
        self.base_max_ph = ph_average + ph_band_size

if __name__ == '__main__':
    start_x = 0
    start_y = 0

    curr_x = start_x 
    curr_y = start_y 

    inner_radius = 800 
    outer_radius = 3000 

    num_planets = 28 
    planets_per_sector = 4

    starting_num = 2000

    namer = NameGenerator()


    def tmp_function(x, y, c_x, c_y, t_base, t_base_max):
        d_x = math.fabs(c_x - x)
        d_y = math.fabs(c_y - y)

        print t_base
        print t_base_max

        min_d = (d_x / inner_radius) * 0.2 * random.random() - 0.1
        max_d = (d_y / inner_radius) * 0.2 * random.random() - 0.1

        t_min = max(0.0, t_base + min_d)
        t_max = min(1.0, t_base_max + max_d)

        print t_min
        print t_max

        return (t_min, t_max)


    def ph_function(x, y, c_x, c_y, ph_base, ph_base_max):
        d_x = math.fabs(c_x - x)
        d_y = math.fabs(c_y - y)

        min_d = (d_x / inner_radius) * 0.4 * random.random() - 0.2
        max_d = (d_y / inner_radius) * 0.4 * random.random() - 0.2

        ph_min = max(0.0, ph_base + min_d)
        ph_max = min(1.0, ph_base_max - max_d)

        return (ph_min, ph_max)

    sector_centroids = []
    num_sectors = max(1, num_planets / planets_per_sector)
    for i in range(num_sectors):
        sector_centroids.append(Centroid(curr_x, curr_y, tmp_function, ph_function))

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
        json_blob['PlanetName'] = namer.get_name() #'Planet %s'%pid
        json_blob['SpacePosition'] = { 'x': x, 'y': y }
        temp = centroid.t_func(x, y, centroid.x, centroid.y, centroid.base_temp, centroid.base_max_temp);
        json_blob['Temperature'] =  { 'Min': temp[0], 'Max': temp[1] }
        ph = centroid.ph_func(x, y, centroid.x, centroid.y, centroid.base_ph, centroid.base_max_ph);
        json_blob['Ph'] =  { 'Min': ph[0], 'Max': ph[1] }
        json_blob['Epoch'] =  1

        db_url = 'http://localhost:8081/persistence/planets/%i'%pid
        print json_blob
        print requests.post(db_url, json=json_blob)
