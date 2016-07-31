from pytim import PyTimGraph
import sys
sys.path.append("..")
from IM_Base import IM_Base
import numpy as np
from numpy.random import randint, binomial, choice, random
from copy import deepcopy

class COINRandomZero(IM_Base):
    def __init__(self, seed_size, graph_file, rounds, iscontextual, cost, 
                context_dims=2, gamma=0.4, epsilon=0.1):
        """------------------------------------------------------------
        seed_size          : number of nodes to be selected
        graph_file         : txt file storing the list of edges of graph
        rounds             : number of rounds the algorithm will run
        context_dims       : number of dimensons in context vectors
        explore_thresholds : lower bounds of under-exploration of nodes
        epsilon            : parameter of TIM algorithm
        ------------------------------------------------------------"""
        # Tunable algorithm parameters
        super().__init__(seed_size, graph_file, rounds, iscontextual, cost)
        self.epsilon = epsilon
        self.cost = cost
        self.explore_thresholds = [((r ** gamma)/100) for r in np.arange(1, rounds+1)]

        self.under_exps = []

        # Initializes the counters and influence estimates
        self.counters = np.array([[0 for edge_idx in range(self.edge_cnt)]
                                  for context_idx in range(self.context_cnt)])
        self.successes = np.zeros_like(self.counters)
        self.inf_ests = np.zeros_like(self.counters)
    
    def __call__(self):
        self.run()
    
    def run(self):
        """------------------------------------------------------------
        High level function that runs the online influence maximization
        algorithm for self.rounds times and reports aggregated regret
        ------------------------------------------------------------"""
        for r in np.arange(1, self.rounds+1):
            print("--------------------------------------------------")
            print("Round: %d" % (r))
            self.get_context()
            context_idx = self.context_classifier(self.context_vector)
            under_explored = self.under_explored_nodes(context_idx, r)

            # If there are enough under-explored edges, return them
            if(len(under_explored) == self.seed_size):
                print("Under Explored Count:%d" % (self.under_exps[-1]))
                exploration_phase = True
                seed_set = under_explored
            
            # Otherwise, run TIM
            else:
                print("TIM")
                exploration_phase = False
                self.dump_graph(self.inf_ests[context_idx], ("tim_"+self.graph_file))
                timgraph = PyTimGraph(bytes("tim_" + self.graph_file, "ascii"), self.node_cnt, self.edge_cnt,
                                                          (self.seed_size - len(under_explored)), bytes("IC", "ascii"))
                tim_set = timgraph.get_seed_set(self.epsilon)
                
                seed_set = list(tim_set)
                seed_set.extend(under_explored)
                timgraph = None

            # Simulates the chosen seed_set's performance in real world
            online_spread, tried_cnts, success_cnts = self.simulate_spread(seed_set)

            if(exploration_phase):
                total_cost = self.active_update(tried_cnts, success_cnts, context_idx, r)
            
            # Oracle run
            real_infs = self.context_influences(self.context_vector)
            self.dump_graph(real_infs, ("tim_"+self.graph_file))
            oracle = PyTimGraph(bytes("tim_" + self.graph_file, "ascii"), self.node_cnt, self.edge_cnt, self.seed_size, bytes("IC", "ascii"))
            oracle_set = list(oracle.get_seed_set(self.epsilon))
            oracle = None
            oracle_spread, _, _ = self.simulate_spread(oracle_set)
            self.regret.append((oracle_spread + total_cost) - online_spread)
            self.spread.append(online_spread)
            self.update_squared_error(real_infs, self.inf_ests[context_idx])
            print("Our Spread: %d" % (online_spread))
            print("Regret: %d" % (self.regret[-1]))
            print("Sq. Error: %2.2f" % (self.squared_error[-1]))   
            
    def under_explored_nodes(self, context_idx, round_idx):
        """------------------------------------------------------------
        Checks which nodes are under-explored based on the trial counts
        of the edges connected to them
        ------------------------------------------------------------"""
        cur_counter = self.counters[context_idx]
        edge_idxs = np.array(np.where(cur_counter < self.explore_thresholds[round_idx-1])[0])
        node_idxs = np.unique(self.edges[edge_idxs][:,0]).tolist()
        self.under_exps.append(len(node_idxs))
        
        under_exp_nodes = choice(node_idxs, self.seed_size, replace=False) \
                          if(len(node_idxs) > self.seed_size) else np.array(node_idxs)
        return under_exp_nodes.tolist()