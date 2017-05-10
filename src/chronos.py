import json
import logging
import requests
import sys
import time

from planet_creator import NameGenerator


###############################################################################
# NOTE: 

class Chronos:

    class ChronosDBHandler:
        # TODO: 
        # Currently using local json files instead of talking to Dynamo
        def __init__(self, config):
            self.url = config.get('DBUrl', 'http://localhost:8081')
            self.rules_version = config.get('RulesVersion', 'POLYMINIS-V1')
            self.name_generator = NameGenerator()

        def get_master_translation_table(self):
            r = requests.get('%s/persistence/gamerules/%s'%(self.url, self.rules_version))
            rules = json.loads(r.content)
            return rules['TraitData']
        
        def get_default_ga_config(self):
            r = requests.get('%s/persistence/gamerules/%s'%(self.url, self.rules_version))
            rules = json.loads(r.content)
            return rules['DefaultGAConfiguration']

        def get_default_translation_table(self):
            # Get Default Traits and Master Translation Table and build
            # a Species Translation Table on the fly

            master_tt = self.get_master_translation_table() 

            r = requests.get('%s/persistence/gamerules/%s'%(self.url, self.rules_version))
            rules = json.loads(r.content)
            traits = rules['DefaultTraits']
            
            trans_table = []
            for trait in traits:
                for m_trait in master_tt:
                    if m_trait['InternalName'] == trait: 
                        trans_table.append({'Tier': m_trait['Tier'], 'Number': m_trait['TID']})
            return trans_table
            

        def get_environment_data(self, planet_id, epoch = -1):

            # TODO
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

            # From Planet Extract - Temperature Ranges, Ph Ranges and Density Ranges
            r = requests.get('%s/persistence/planets/%s'%(self.url, planet_id))
            logging.debug("Planet Data %s"%r.content)
            planet_data = json.loads(r.content) 
            environment["Environment"].update({
                "Temperature": planet_data.get("Temperature", {"Max": 0.5, "Min": 0.5}),
                "Ph": planet_data.get("Ph", {"Max": 0.5, "Min": 0.5}),
                "Density": planet_data.get("Density", 0.5)
            })

            return environment

        def get_species_params(self, planet_id, epoch):

            planetEpoch = "%s%s"%(planet_id, epoch)
            r = requests.get('%s/persistence/speciesinplanet/%s'%(self.url, planetEpoch))

            logging.debug(r.content)
            species = json.loads(r.content)
            return species['Items']

        def save_epoch_to_db(self, p_species_data, epoch_data, planet_id, epoch_num): 

            species_data = list(p_species_data)

            planetEpoch = '%i%i'%(planet_id, epoch_num) 


            # In case species was added after we started the sim.
            try:
                lapsed_species = self.get_species_params(planet_id, epoch_num)  
            except Exception: 
                lapsed_species = []

            percentages = {}
            lapsed = False
            for ls in lapsed_species:
                speciesName = ls['SpeciesName']
                percentages[speciesName] = ls['Percentage']
                #species_data.append(ls)
                lapsed = False 

            # Get all percentages after sim
            for sd in species_data:
                speciesName = sd['SpeciesName']
                sd['PlanetEpoch'] = planetEpoch
                percentages[speciesName] = sd['Percentage']

            perc_total = 0.0
            for k in percentages.keys():
                perc_total += percentages[k]

            # Normalize back - In case of a lapsed set of specie we re-normalize to adjust for the new presence
            if perc_total > 1.0 or lapsed:
                for speciesname in percentages:
                    percentages[speciesname] /= perc_total
                ##map(lambda speciesname: percentages[speciesname] /= perc_total, percentages)
                for speciesd in species_data:
                    speciesd['Percentage'] = percentages[speciesd['SpeciesName']]
                ##map(lambda s_data: s_data['Percentage'] = percentages[s_data['SpeciesName']], species_data)

            for sd in species_data:
                print sd['SpeciesName']
                r = requests.post('%s/persistence/speciesinplanet/%s/%s'%(self.url, planetEpoch, speciesName), json=sd)

            payload = {}
            payload['PlanetId'] = planet_id 
            payload['EpochNum'] = epoch_num
            payload['Percentages'] = percentages
            r = requests.post('%s/persistence/epochs/%s/%s'%(self.url, planet_id, epoch_num), json=payload)

            # Save the latest epoch in the planet
            planet_payload = { 'PlanetId': planet_id, 'Epoch': epoch_num }
            r = requests.put('%s/persistence/planets/%s'%(self.url, planet_id), json=planet_payload)


        def new_species_payload(self):
            ret = {}
            ret['GAConfiguration'] = self.get_default_ga_config()
            ret['TranslationTable'] = self.get_default_translation_table()
            ret['SpeciesName'] = self.name_generator.get_name() 
            ret['CreatorName'] = 'Chronos'
            ret['Percentage'] = 1.0
            ret['InstinctWeights'] = {}
            return [ret]

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

            if species_list == None:
                logging.info("ERROR!!!")
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

        def wait_for_epoch(self, epoch, timeout=5000):
            waited = 0
            wait = 0.25
            while True:
                time.sleep(wait)
                waited += wait
                r = requests.get('%s/simulations/%i/epochs/%i'%(self.url, self.sim_inx, epoch))
                epoch_json = json.loads(r.content); 
                if epoch_json.get('Evaluated', False):
                    break
                elif waited >= timeout:
                    raise Exception('Timeout!')
        

    def __init__(self, config):
        self.db_handler = self.ChronosDBHandler(config)
        self.sim_handler = self.ChronosSimHandler(config)

    def run(self, epochs=1, new=False, load=[], planet_list=[], save=False, dump=False, save_every=-10000):
#
#        Contract: Any Species in the DB is ready to be simulated in Game:
#           - It's been evaluated
#   
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



        # Planet list is just calling run with load = epoch + that planet

        if len(planet_list) > 0:
            logging.info('Planet List')
            if len(planet_list) < 2:
                raise argparse.ArgumentError(None, 'A')
            epoch = planet_list.pop(0)
            for pid in planet_list: 
               self.run(epochs=epochs, new=new, load=[pid, epoch], planet_list=[], save=save, dump=dump, save_every=save_every)
            return

        if (not new and len(load) != 2):
            raise argparse.ArgumentError(None, '%s %i %i'%(new, len(load), len(planet_list)))
        if (new and len(load) == 2):
            raise argparse.ArgumentError(None, 'C')

        master_tt = self.db_handler.get_master_translation_table()

        species = None
        e_num = -1;
        if len(load) == 2: 
            planet_id = int(load[0])
            e_num = int(load[1])
            species = self.db_handler.get_species_params(planet_id=planet_id, epoch=e_num)
        if new:
            e_num = 4000;
            planet_id = 9090; # TODO: Semi Hardcoded
            species = self.db_handler.new_species_payload()

        epoch = self.db_handler.get_environment_data(planet_id=planet_id, epoch=e_num)
        payload = { 'MasterTranslationTable': master_tt,
                        'EpochNum': e_num,
                        'Species': species,
                        'SimulationType': 'Solo Run' }
        payload['Epoch'] = epoch 

        scenarios = self.prepare_scenarios(epoch)

        payload['Scenarios'] = scenarios

        print scenarios

        starting_epoch = e_num

        self.sim_handler.add_simulation()
        
        logging.info('Starting Loop...')

        while(e_num < (starting_epoch + epochs)):
            then = time.time()


            # The first time we get the data from the db, afterwards we get it from the Simulation
            if e_num > starting_epoch:
               # payload['Epoch'] = self.sim_handler.get_epoch_data(e_num)
                payload = { 'MasterTranslationTable': master_tt,
                        'EpochNum': e_num,
                        'SimulationType': 'Solo Run',
                        'Epoch': epoch }
                # Get the generation now that has been evaluated
                new_species = self.sim_handler.get_species_data(e_num)
                filter(lambda x: x != None, map(lambda old, new: old.update(new) if old != None and new != None else new, species, new_species))
                payload['Species'] = species

            logging.info('Advancing Epoch %i...'%(e_num))
            self.sim_handler.advance_epoch(payload)
            e_num += 1
            ## Get the fresh generation
            new_species = self.sim_handler.get_species_data(e_num)
            if species == None or new_species == None:
                logging.info("%s %s", species, new_species)

            # Filter out extinctions and handle new species gracefully
            filter(lambda x: x != None, map(lambda old, new: old.update(new) if old != None and new != None else new, species, new_species))

            logging.info('... Finished')

            # New Epoch
            new_epoch = { 'MasterTranslationTable': master_tt,
                          'EpochNum': e_num,
                          'SimulationType': 'Solo Run' }

            new_epoch['Species'] = species
            new_epoch['Epoch'] = epoch 
            new_epoch['Scenarios'] = scenarios


            logging.info('Simulating Epoch %i...'%(e_num))
            self.sim_handler.simulate_epoch(new_epoch)
            ## Wait for the epoch to be evaluated
            self.sim_handler.wait_for_epoch(e_num)
            logging.info('...Finished')

            is_last_epoch = not (e_num < (starting_epoch + epochs))

            if ( (is_last_epoch and save) or e_num % save_every == 0):
                logging.info('Recording Epoch %i into DB...'%(e_num))


                XXX = self.sim_handler.get_species_data(e_num)
                map(lambda old, new: old.update(new), species, XXX)

                self.db_handler.save_epoch_to_db(species, epoch, planet_id, e_num)
                logging.info('...Done')

            logging.info('...Loop took (%i s)', (time.time() - then))

            if dump:
                logging.info('...Dumping Species')
                logging.info()

    def prepare_scenarios(self, env):
        env = env["Environment"]
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
                        new_scenario[k] = dict(new_scenario[k]) # Create a new object to avoid polluting other tests
                        new_scenario[k].update(scenario[k])
                    else:
                        new_scenario[k] = scenario[k]

            if scenario["Metadata"].has_key("RequiresData"):
                for field in scenario["Metadata"]["RequiresData"]:
                    obj = scenario 
                    for path in field.split('.'):
                        if path == 'LIST':
                            is_list = True
                            break
                        obj = obj[path]
                    
                    #TODO: This was looking good until the list vs dict happened,
                    #      probably a good lambda can fix this for us
                    if is_list:
                        for e in obj:
                            for sub_f in e:
                                if e[sub_f] == "MAX_TEMPERATURE": 
                                    e[sub_f] = env['Temperature']["Max"]
                                if e[sub_f] == "MIN_TEMPERATURE": 
                                    e[sub_f] = env["Temperature"]["Min"]
                    else:
                        for sub_f in obj:
                            if obj[sub_f] == "MAX_TEMPERATURE": 
                                obj[sub_f] = env["Temperature"]["Max"]
                            if obj[sub_f] == "MIN_TEMPERATURE": 
                                obj[sub_f] = env["Temperature"]["Min"]

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
    parser.add_argument('-P', '--planet-list', nargs='+', metavar='PlanetList', help='[Epoch] [Planets] to load and simulate', type=int, default=[])

    args = parser.parse_args()

    config = {'DBUrl': args.db_url,
              'SimUrl': args.sim_url}
    chronos = Chronos(config)
    try:
        chronos.run(epochs=args.advance, new=args.new, load=args.load, planet_list=args.planet_list, save=args.save, save_every=args.save_every)
    except argparse.ArgumentError as e:
        logging.error(e)
        logging.error('Error Please check your usage:')
        parser.print_help()
