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

        def get_environment_data(self, planet_id, epoch = -1):
            r = requests.get('%s/persistence/planets/%s'%(self.url, planet_id))
            logging.debug(r.content)

            # From Planet Extract - Temperature Ranges, Ph Ranges and Density Ranges
            # From Game Rules DB extract Default Sensors, Default Dimensions and Run Configuration

            environment = json.loads('''
                 {
                    "Environment":
                     {
                        "DefaultSensors":["positionx","positiony","orientation","lastmovesucceded", "timeglobal", "timesubstep"],
                        "Dimensions":{"x":5000.0,"y":5000.0},
                        "SpeciesSlots":3,
                        "AddBorder": true 
                     },"MaxSteps":100,"Proportions":[],"Restarts":1,"Substeps":4
                }
                ''')

            planet_data = json.loads(r.content) 
            environment["Environment"].update({
                "Temperature": planet_data.get("Temperature", {}),
                "Ph": planet_data.get("Ph", {}),
                "Density": planet_data.get("Density", {})
            })

            return environment

        def get_species_params(self, planet_id, epoch):

            planetEpoch = "%s%s"%(planet_id, epoch)
            r = requests.get('%s/persistence/speciesinplanet/%s'%(self.url, planetEpoch))

            logging.debug(r.content)
            species = json.loads(r.content)
            return species['Items']

        def save_epoch_to_db(self, species_data, epoch_data, planet_id, epoch_num): 

            planetEpoch = '%i%i'%(planet_id, epoch_num) 


            for sd in species_data:
                speciesName = sd['SpeciesName']
                sd['PlanetEpoch'] = planetEpoch
                r = requests.post('%s/persistence/speciesinplanet/%s/%s'%(self.url, planetEpoch, speciesName), json=sd)

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
            logging.info("Sending Simulation Request...")
            r = requests.post('%s/simulations/%i/epochs/simulate'%(self.url, self.sim_inx), json=payload)
            return r.content

    def __init__(self, config):
        self.db_handler = self.ChronosDBHandler(config)
        self.sim_handler = self.ChronosSimHandler(config)

    def run(self, epochs=1, new=False, load=[], save=False, dump=False, save_every=-10000):
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

        species = None
        e_num = -1;
        if len(load) == 2: 
            planet_id = int(load[0])
            e_num = int(load[1])
            species = self.db_handler.get_species_params(planet_id=planet_id, epoch=e_num)
            epoch = self.db_handler.get_environment_data(planet_id=planet_id, epoch=e_num)
            payload = { 'MasterTranslationTable': master_tt,
                            'EpochNum': e_num,
                            'Species': species,
                            'SimulationType': 'Solo Run' }
            payload['Epoch'] = epoch 

        scenarios = self.prepare_scenarios(None)

        payload['Scenarios'] = scenarios

        starting_epoch = e_num

        self.sim_handler.add_simulation()
        
        logging.info('Starting Loop...')
#        logging.info('Simulating Epoch %i...'%(e_num))
#        self.sim_handler.simulate_epoch(payload)
#        logging.info('...Finished')

        while(e_num <= (starting_epoch + epochs)):
            then = time.time()


            # The first time we get the data from the db, afterwards we get it from the Simulation
            if e_num > starting_epoch:
               # payload['Epoch'] = self.sim_handler.get_epoch_data(e_num)
                payload = { 'MasterTranslationTable': master_tt,
                        'EpochNum': e_num,
                        'SimulationType': 'Solo Run',
                        'Epoch': epoch }
                map(lambda old, new: old.update(new), species, self.sim_handler.get_species_data(e_num))
                payload['Species'] = species

            logging.info('Advancing Epoch %i...'%(e_num))
            self.sim_handler.advance_epoch(payload)        
            logging.info('... Finished')


            # New Epoch
            e_num += 1
            new_epoch = { 'MasterTranslationTable': master_tt,
                          'EpochNum': e_num,
                          'SimulationType': 'Solo Run' }

            new_epoch['Species'] = species
            new_epoch['Epoch'] = epoch 
            new_epoch['Scenarios'] = scenarios


            logging.info('Simulating Epoch %i...'%(e_num))
            self.sim_handler.simulate_epoch(new_epoch)
            map(lambda old, new: old.update(new), species, self.sim_handler.get_species_data(e_num))
            logging.info('...Finished')


            is_last_epoch = not (e_num < (starting_epoch + epochs))

            if ( (is_last_epoch and save) or e_num % save_every == 0):
                logging.info('Recording Epoch %i into DB...'%(e_num))
                self.db_handler.save_epoch_to_db(species, epoch, planet_id, e_num)
                logging.info('...Done')

            logging.info('...Loop took (%i s)', (time.time() - then))

            if dump:
                logging.info('...Dumping Species')
                logging.info()

    def prepare_scenarios(self, env):
        # This is an array of scenarios with default values.
        # Per-Planet values can be added on top (Like Temperature, etc...) to customize the run
        config = json.loads(file('default_scenario_configuration.json').read())
        scenarios = config["Scenarios"]
        template = config["Template"]
        
        new_scenarios = []
        for scenario in scenarios:
            new_scenario = dict(template)

            for k in new_scenario.keys():
                if scenario.has_key(k):
                    if isinstance(scenario[k], dict):
                        new_scenario[k].update(scenario[k])
                    else:
                        new_scenario[k] = scenario[k]

            new_scenarios.append(new_scenario)


        return new_scenarios
        

if __name__ == '__main__':


    def json_file(path_to_file):
        return json.loads(file(path_to_file).read())

    import argparse
    # TODO: Config should come from command line and / or a file
    # (How would this work on Lambda ?)

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Chronos, the Polyminis God of Time')

    parser.add_argument('--db_url',  metavar='DBUrl',  type=str, help='URL of the Persistence Server', default='http://localhost:8081')

    parser.add_argument('--sim_url',  metavar='SimUrl',  type=str, help='URL of the Simulation Server', default='http://localhost:8082')

    parser.add_argument('--save', action='store_true')
    parser.add_argument('--save_every', metavar='SaveEvery', type=int, help='Save into the db every [N] epochs', default=-1000)

    parser.add_argument('--dump', action='store_true', help='Dump result after generation')

    parser.add_argument('-A', '--advance', dest='advance', metavar='Advance', type=int, help='How many epochs to advance', default=1, const=1, nargs='?')
    parser.add_argument('-N', '--new', action='store_true', help='Create Simulation state from scratch')
    parser.add_argument('-L', '--load', nargs=2, metavar='Load', help=' [PlanetId] [Epoch] to load and simulate', default=[])

    args = parser.parse_args()

    config = {'DBUrl': args.db_url,
              'SimUrl': args.sim_url}
    chronos = Chronos(config)
    try:
        chronos.run(epochs=args.advance, new=args.new, load=args.load, save=args.save, save_every=args.save_every)
    except argparse.ArgumentError:
        logging.error('Error Please check your usage:')
        parser.print_help()
