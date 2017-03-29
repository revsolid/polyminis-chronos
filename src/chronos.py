import json
import logging
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
            self.url = config.get('DBUrl', 'http://localhost:8081')
            self.rules_version = config.get('RulesVersion', 'POLYMINIS-V1')

        def get_master_translation_table(self):
            r = requests.get('%s/persistence/gamerules/%s'%(self.url, self.rules_version))
            rules = json.loads(r.content)
            return rules['TraitData']

        def get_planet_data(self, planet_id, epoch = -1):
            r = requests.get('%s/persistence/planets/%s'%(self.url, planet_id))
            logging.info(r.content)
            
            return json.loads('''
                 {
                    "Environment":
                     {
                        "DefaultSensors":["positionx","positiony","orientation","lastmovesucceded"],
                        "Dimensions":{"x":100.0,"y":100.0},
                        "SpeciesSlots":3
                     },"MaxSteps":100,"Proportions":[],"Restarts":1,"Substeps":4
                }
                ''')

        def get_species_params(self, planet_id, epoch):

            planetEpoch = "%s%s"%(planet_id, epoch)
            r = requests.get('%s/persistence/speciesinplanet/%s'%(self.url, planetEpoch))

            logging.info(r.content)
            species = json.loads(r.content)
            return species['Items']

        def save_epoch_to_db(self, species_data, epoch_data, planet_id, epoch_num): 

            planetEpoch = '%i%i'%(planet_id, epoch_num) 


            for sd in species_data:
                speciesName = sd['SpeciesName']
                sd['PlanetEpoch'] = planetEpoch
                r = requests.post('%s/persistence/speciesinplanet/%s/%s'%(self.url, planetEpoch, speciesName), json=sd)
                ##print('%s/persistence/speciesinplanet/%s/%s'%(self.url, planetEpoch, speciesName))
                ##print(species_data)

    class ChronosSimHandler:
        def __init__(self, config):
            self.url = config.get('SimUrl', 'http://localhost:8082')
            self.sim_inx = 0

        def get_epoch_data(self, epoch):
            r = requests.get('%s/simulations/%i/epochs/%i/db'%(self.url, self.sim_inx, epoch))
            return json.loads(r.content)

        def get_species_data(self, epoch):
            species_list = []
            while len(species_list) == 0:
                time.sleep(0.25)
                r = requests.get('%s/simulations/%i/epochs/%i/db/species'%(self.url, self.sim_inx, epoch))
                species = json.loads(r.content)
                for s_data in species.values():
                    species_list.append(s_data)
            return species_list 
            
        def add_simulation(self):
            r = requests.post('%s/simulations/add'%(self.url))
            res = json.loads(r.content)
            self.sim_inx = res.get('SimulationId', 0)

        def advance_epoch(self, payload):
            r = requests.post('%s/simulations/%i/epochs/advance'%(self.url, self.sim_inx), json=payload)
            return r.content

        def simulate_epoch(self, payload):
            r = requests.post('%s/simulations/%i/epochs/simulate'%(self.url, self.sim_inx), json=payload)
            return r.content

    def __init__(self, config):
        self.db_handler = self.ChronosDBHandler(config)
        self.sim_handler = self.ChronosSimHandler(config)

    def run(self, epochs=1, new=False, load=[], save=False):
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

        if (not new and len(load) != 2):
            raise argparse.ArgumentError(None, '')
        if (new and len(load) == 2):
            raise argparse.ArgumentError(None, '')

        master_tt = self.db_handler.get_master_translation_table()

        if len(load) == 2: 
            planet_id = int(load[0])
            e_num = int(load[1])
            species = self.db_handler.get_species_params(planet_id=planet_id, epoch=e_num)
            epoch = self.db_handler.get_planet_data(planet_id=planet_id, epoch=e_num)
            payload = { 'MasterTranslationTable': master_tt,
                            'EpochNum': e_num,
                            'Species': species,
                            'SimulationType': 'Solo Run' }
            payload['Epoch'] = self.db_handler.get_planet_data(planet_id)
        else:
            planet_id = 1414
            e_num = 1 
            payload = json.loads(file('temp_data.json').read())

        starting_epoch = e_num

        self.sim_handler.add_simulation()
        
        logging.info('Simulating Epoch %i...'%(e_num))
        self.sim_handler.simulate_epoch(payload)
        logging.info('...Finished')


        while(e_num <= (starting_epoch + epochs)):
            map(lambda old, new: old.update(new), species, self.sim_handler.get_species_data(e_num))

            payload = { 'MasterTranslationTable': master_tt,
                        'EpochNum': e_num,
                        'Species': species,
                        'SimulationType': 'Solo Run' }
            payload['Epoch'] = self.sim_handler.get_epoch_data(e_num)

            logging.info('Advancing Epoch %i...'%(e_num))
            self.sim_handler.advance_epoch(payload)        
            logging.info('... Finished')

            e_num += 1


            new_epoch = { 'MasterTranslationTable': master_tt,
                          'EpochNum': e_num,
                          'SimulationType': 'Solo Run' }

            map(lambda old, new: old.update(new), species, self.sim_handler.get_species_data(e_num))
            epoch = self.sim_handler.get_epoch_data(e_num);

            new_epoch['Species'] = species
            new_epoch['Epoch'] = epoch 


            ## Skip simulating the last epoch as it is not going to be used
            if (e_num < (starting_epoch + epochs)):
                logging.info('Simulating Epoch %i...'%(e_num))
                self.sim_handler.simulate_epoch(new_epoch)
                logging.info('...Finished')
            else:
                if (save):
                    logging.info('Recording Epoch %i into DB...'%(e_num))
                    self.db_handler.save_epoch_to_db(species, epoch, planet_id, e_num)
                    logging.info('...Done')
                break


if __name__ == '__main__':


    def json_file(path_to_file):
        return json.loads(file(path_to_file).read())

    import argparse
    # TODO: Config should come from command line and / or a file
    # (How would this work on Lambda ?)

    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Chronos, the Polyminis God of Time')

    parser.add_argument('--db_url',  metavar='DBUrl',  type=str, help='URL of the Persistence Server', default='http://localhost:8081')

    parser.add_argument('--sim_url',  metavar='SimUrl',  type=str, help='URL of the Simulation Server', default='http://localhost:8082')

    parser.add_argument('--payload', metavar='Payload', type=str, help='Raw payload to send')
    parser.add_argument('--payload_json', metavar='PayloadJson', type=json_file, help='Payload File (Json)')
    parser.add_argument('--save', action='store_true')

    parser.add_argument('-A', '--advance', dest='advance', metavar='Advance', type=int, help='How many epochs to advance', default=1, const=1, nargs='?')
    parser.add_argument('-N', '--new', action='store_true', help='Create Simulation state from scratch')
    parser.add_argument('-L', '--load', nargs=2, metavar='Load', help=' [PlanetId] [Epoch] to load and simulate', default=[])

    args = parser.parse_args()

    config = {'DBUrl': args.db_url,
              'SimUrl': args.sim_url}
    chronos = Chronos(config)
    try:
        chronos.run(epochs=args.advance, new=args.new, load=args.load, save=args.save)
    except argparse.ArgumentError:
        logging.error('Error Please check your usage:')
        parser.print_help()
