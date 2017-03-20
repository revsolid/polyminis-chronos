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
            self.url = config.get('SimUrl', 'http://localhost:8081')

        def get_master_translation_table(self):
            return json.loads('[{"TID":1,"Tier":"TierI","Trait":"speedtrait"},{"TID":3,"Tier":"TierI","Trait":"hormov"},{"TID":2,"Tier":"TierI","Trait":"vermov"}]')

        def get_planet_data(self, planet_id, epoch = -1):
           return json.loads('''
                {
                    "Environment":
                     {
                        "DefaultSensors":["positionx","positiony","orientation","lastmovesucceded"],
                        "Dimensions":{"x":100.0,"y":100.0},
                        "SpeciesSlots":2
                     },"MaxSteps":50,"Proportions":[],"Restarts":1,"Substeps":4
                }
                ''')

        def get_species_params(self, planet_id=-1, epoch=-1, name="Test Species"):
            return json.loads('''
                    [{
                        "GAConfiguration":
                        {
                            "FitnessEvaluators":
                            [
                                {"EvaluatorId":"overallmovement","Weight":2.5},
                                {"EvaluatorId":"distancetravelled","Weight":2.0},
                                {"EvaluatorId":"shape","Weight":5.0},
                                {"EvaluatorId":"alive","Weight":10.0},
                                {"EvaluatorId":"positionsvisited","Weight":0.5},
                                {"EvaluatorId":"targetposition","Position":{"x":1.0,"y":1.0}, "Weight":15.0},
                                {"EvaluatorId":"targetposition","Position":{"x":1.0,"y":0.0}, "Weight":15.0}
                            ], 
                            "GenomeSize":8,
                            "MaxGenerations":50,
                            "PercentageElitism":0.20000000298023224,
                            "PercentageMutation":0.10000000149011612,
                            "PopulationSize":50,
                            "InstinctWeights":{}
                        },
                        "Name":"%s",
                        "TranslationTable":[{"Number":2, "Tier":"TierI"}, {"Number":1, "Tier":"TierI"}, {"Number":3, "Tier":"TierI"}]
                    }]
                    '''%name)
            

    class ChronosSimHandler:
        def __init__(self, config):
            self.url = config.get('SimUrl')
            self.sim_inx = 0

        def get_epoch_data(self, epoch):
            r = requests.get("%s/simulations/%i/epochs/%i/db"%(self.url, self.sim_inx, epoch))
            return json.loads(r.content)

        def get_species_data(self, epoch):
            r = requests.get("%s/simulations/%i/epochs/%i/db/species"%(self.url, self.sim_inx, epoch))
            species = json.loads(r.content)
            species_list = []
            for s_data in species.values():
                species_list.append(s_data)
            return species_list 
            
        def add_simulation(self):
            r = requests.post("%s/simulations/add"%(self.url))
            res = json.loads(r.content)
            self.sim_inx = res.get('SimulationId', 0)

        def advance_epoch(self, payload):
            r = requests.post("%s/simulations/%i/epochs/advance"%(self.url, self.sim_inx), json=payload)
            return r.content

        def simulate_epoch(self, payload):
            r = requests.post("%s/simulations/%i/epochs/simulate"%(self.url, self.sim_inx), json=payload)
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
            raise argparse.ArgumentException('')
        if (new and len(load) == 2):
            raise argparse.ArgumentException('')


        if len(load) == 2: 
            planet_id = load[0]
            e_num = load[1]
            species = self.db_handler.get_species_params(planet_id=planet_id, epoch=e_num)
            epoch = self.db_handler.get_planet_data(planet_id=planet_id, epoch=e_num)
            payload = { "MasterTranslationTable": master_tt,
                            "EpochNum": e_num,
                            "Species": species }
            payload["Epoch"] = epoch 
        else:
            planet_id = -1
            e_num = 1 
            payload = json.loads(file('temp_data.json').read())

        starting_epoch = e_num

        self.sim_handler.add_simulation()
        master_tt = self.db_handler.get_master_translation_table()
        
        self.sim_handler.simulate_epoch(payload)
        time.sleep(5)

        while(e_num <= (starting_epoch + epochs)):
            species = self.sim_handler.get_species_data(e_num)

            payload = { "MasterTranslationTable": master_tt,
                        "EpochNum": e_num,
                        "Species": species }
            payload["Epoch"] = self.sim_handler.get_epoch_data(e_num)
            self.sim_handler.advance_epoch(payload)        

            time.sleep(5)

            e_num += 1

            new_epoch = { "MasterTranslationTable": master_tt,
                          "EpochNum": e_num }

            species = self.sim_handler.get_species_data(e_num)

            new_epoch["Species"] = species
            new_epoch["Epoch"] = self.sim_handler.get_epoch_data(e_num)

            print new_epoch 
            self.sim_handler.simulate_epoch(new_epoch)

            time.sleep(5)


if __name__ == '__main__':


    def json_file(path_to_file):
        return json.loads(file(path_to_file).read())

    import argparse
    # TODO: Config should come from command line and / or a file
    # (How would this work on Lambda ?)

    parser = argparse.ArgumentParser(description='Chronos, the Polyminis God of Time')

    parser.add_argument('--db_url',  metavar='DBUrl',  type=str, help='URL of the Persistence Server', default='http://localhost:8081')

    parser.add_argument('--sim_url',  metavar='SimUrl',  type=str, help='URL of the Simulation Server', default='http://localhost:8080')

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
    chronos.run(epochs=args.advance, new=args.new, load=args.load)
