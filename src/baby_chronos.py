import json
import requests
import sys
import time


###############################################################################
# NOTE: 

class Chronos:

    class ChronosDBHandler:
        # TODO: 
        # Currently using local json files instead of talking to Dynamo
        def __init__(self, config):
            pass

    class ChronosSimHandler:
        def __init__(self, config):
            self.url = "http://localhost:8080"
            self.sim_inx = 0

        def get_epoch_data(self, epoch):
            r = requests.get("%s/simulations/%i/epochs/%i/db"%(self.url, self.sim_inx, epoch))
            print r.content
            return json.loads(r.content)

        def get_species_data(self, epoch):
            r = requests.get("%s/simulations/%i/epochs/%i/db/species"%(self.url, self.sim_inx, epoch))
            print r.content
            species = json.loads(r.content)
            species_list = []
            for s_data in species.values():
                species_list.append(s_data)
            return species_list 
            
        def advance_epoch(self, payload):
            r = requests.post("%s/simulations/%i/epochs/advance"%(self.url, self.sim_inx), json=payload)
            print r.content
            return r.content

        def simulate_epoch(self, payload):
            r = requests.post("%s/simulations/%i/epochs/simulate"%(self.url, self.sim_inx), json=payload)
            print r.content
            return r.content

    def __init__(self, config):
        self.db_handler = self.ChronosDBHandler(config)
        self.sim_handler = self.ChronosSimHandler(config)

    def run(self):
#        1. Talk to Almanac to get information from the Planet we're
#        simulating and extra config. 
#
#        2. Advance Simulation (SimHandler.advance_epoch)
#
#        3. Upload that resulting Sim data to the Simulation server (SimHandler.simulate_epoch)
#
#        4. Save the data back on the Almanac
#
#        Repeat as needed (Steps 2 & 3 could repeat if more than one Epoch is supposed to be advanced)

        e_num = 1 
        master_tt = json.loads('[{"TID":1,"Tier":"TierI","Trait":"speedtrait"},{"TID":3,"Tier":"TierI","Trait":"hormov"},{"TID":2,"Tier":"TierI","Trait":"vermov"}]')

        while(e_num <= 5):
            species = self.sim_handler.get_species_data(e_num)

            payload = { 'MasterTranslationTable': master_tt,
                        'EpochNum': e_num,
                        'Species': species }
            payload['Epoch'] = self.sim_handler.get_epoch_data(e_num)
            print payload
            self.sim_handler.advance_epoch(payload)        

            time.sleep(5)

            e_num += 1

            new_epoch = { 'MasterTranslationTable': master_tt,
                          'EpochNum': e_num }

            species = self.sim_handler.get_species_data(e_num)

            new_epoch['Species'] = species
            new_epoch['Epoch'] = self.sim_handler.get_epoch_data(e_num)

            self.sim_handler.simulate_epoch(new_epoch)

            time.sleep(5)


if __name__ == '__main__':
    # TODO: Config should come from command line and / or a file
    # (How would this work on Lambda ?)
    config = {}
    chronos = Chronos(config)
    chronos.run()
