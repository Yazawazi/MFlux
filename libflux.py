# Copyleft 2016 Forrest Sheng Bao, Wu Jiang, and Stephen Gang Wu
# Released under GNU Affero General Public License Version 3.0
# See http://www.gnu.org/licenses/agpl-3.0.en.html
#
# For updated version, check our Git repository at
# https://bitbucket.org/forrestbao/mflux
# or our website
# http://mflux.org
#
# Cite this work: Wu et al., Rapid prediction of bacterial heterotrophic
# fluxomics using machine learning and constraint programming,
# PLoS Computational Biology, 2016, DOI: 10.1371/journal.pcbi.1004838
#
# This file contains most functions for flux prediction in MFlux

import html
import numpy
import pickle
import time
import collections
import sys
import itertools
import cvxopt, cvxopt.solvers


def quadprog_adjust(Substrates, Fluxes, Boundary_dict, pushLastWords, Debug=False, Label_scalers=None):
    """adjust values from ML
    Parameters
    ============
    Substrates: OrderedDict, keys as integers and values as floats, e.g., {1:0.25, 2:0, 3:0.75, ...}
    Fluxes: Dict, keys as integers and values as floats, e.g., {1:99.5, 2:1.1, ...}
    Debug: Boolean, True for showing debug info and False (default) for no.
    Label_scaler: sklearn.preprocessing.standardScaler or .MinMaxScaler
                  Forward transform is from fluxes in true range to scaled range
                  Inverse transform is from scaled range to true range
    Boundary_dict: Upper boundaries and lower boundaries for 29 fluxes, depending on user inputs,
                   e.g., {"lb29":999, "ub8":50}, populate ub and lb inequalities from them
    Returns
    =========
     Solution: Dict, keys as integers and values as floats, e.g., {1:99.5, 2:1.1, ...}
    Notes
    ========
    In Substrates, the mapping from keys to real chemicals is as follows:
        1. Glucose
        2. Fructose
        3. Galactose
        4. Gluconate
        5. Glutamate
        6. Citrate
        7. Xylose
        8. Succinate
        9. Malate
        10. Lactate
        11. Pyruvate
        12. Glycerol
        13. Acetate
        14. NaHCO3

    Formulation of quadratic problems in MATLAB optimization toolbox are different from that in cvxopt.
    Here is a mapping between variables
    * H => P (the quadratic terms in objective function)
    * f => q (the linear terms in objective function)
    * A and eyes for boundaries => G (coefficients for linear terms in inequality constraints)
	* b, -lb, ub => h (coefficients for constant terms in inequality constraints)
    * Aeq => A
    * Beq => b
    Unimplemented features:
    1. Using scaled values for quadprog
    Example
    ============
    >>> Substrates = {1:1, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0, 13:0, 14:0}
    >>> Fluxes = {1: 100.0, 2: -2.7159, 3: 15.2254, 4: 17.7016, 5: 110.9973, 6: 91.8578, 7: 137.7961, 8: 91.1558, 9: -0.7373, 10: 94.1518, 11: 24.1126, 12: 21.231, 13: 2.8816, 14: 11.0324, 15: 10.1986, 16: 11.0324, 17: 79.4203, 18: 79.4203, 19: 67.9442, 20: 67.8806, 21: 79.3567, 22: 79.3567, 23: 64.0876, 24: 11.4761, 25: 70.0392, 26: -1.2424, 27: 0.0059, 28: 23.2159, 29: 26.7451}
    >>> import libflux
    >>> libflux.quadprog_adjust(Substrates, Fluxes, {}, Debug=True)
    >>> import cPickle
    >>> Label_scalers = cPickle.load(open("label_scalers.p", "r"))
    >>> libflux.quadprog_adjust(Substrates, Fluxes, {}, Debug=True, Label_scalers = Label_scalers)
    >>> libflux.quadprog_adjust(Substrates, Fluxes, {"ub1":50}, Debug=True, Label_scalers = Label_scalers)
    """


    Substrate2Index= {"glucose":1, "galactose":3, "fructose":2, "gluconate":4, "glutamate":5, "citrate":6, "xylose":7, "succinate":8, "malate":9, "lactate":10, "pyruvate":11, "glycerol":12, "acetate":13}

    Ubs = numpy.array([[100,99.5,99.3,99.3,216.6,
           196.2,232,213.1,135,151.4,
           113.7,94.1,41.2,47.5,71,
           47.5,189,189,189,194,
           194,194,181.5,55,148,
           193.2,151,149.8,104.2043714]])
    Ubs = Ubs.transpose() # turn it into column vector, 29x1

    Lbs = numpy.array([[0,-99.9,-51.5,-51.5,-13.5,
           -23.3,-36,-7.9,-144,0,
           0,-33,-94.4,-2,-6.6,
           -2,0,-0.1,-0.1,0,
           -105,-106,-144.3,0,0,
           0,-100,-67.60986805,-13.5]])
    Lbs = Lbs.transpose() # turn it into column vector, 29x1

    Aineq_bound, Bineq_bound = populate_boundary_inequalities(Boundary_dict)

    Aineq = numpy.zeros((12+1, 29+1)) # the plus 1 is to tackle MATLAB 1-index
    Aineq[1,1] = 1; Aineq[1,2] = -1; Aineq[1,10] = -1;
#    Aineq[2,2] = 1;Aineq[2,3] = -1; Aineq[2,15] = 1; Aineq[2,16] = 1;
#    Aineq[3,3] = 1; Aineq[3,4] = 1; Aineq[3,5] = -1;Aineq[3,14] = 1; Aineq[3,15] = 1; Aineq[3,16] = 1; Aineq[3,25] = 1;
    Aineq[2,2] = 1;Aineq[2,3] = -1; Aineq[2,16] = 2;
    Aineq[3,3] = 1; Aineq[3,4] = 1; Aineq[3,5] = -1;Aineq[3,14] = 1; Aineq[3,25] = 1;
    Aineq[4,5] = 1; Aineq[4,6] = -1;

    if Substrates[Substrate2Index["lactate"]] + Substrates[Substrate2Index["glutamate"]] + \
            Substrates[Substrate2Index["acetate"]] + Substrates[Substrate2Index["citrate"]] + \
            Substrates[Substrate2Index["pyruvate"]] >= 0.5:
        Aineq[5,6] = 1; Aineq[5,7] = -1; Aineq[5,28] = -1;

#    Aineq[5,6] = 1; Aineq[5,7] = -1; Aineq[5,28] = -1;
    Aineq[6,7] = 1; Aineq[6,8] = -1; Aineq[6,25] = 1;Aineq[6,27] = -1; Aineq[6,29] = 1;
    Aineq[7,8] = 1; Aineq[7,9] = -1; Aineq[7,17] = -1;Aineq[7,24] = -1; Aineq[7,26] = -1;
    Aineq[8,13] = 1; Aineq[8,14] = -1;
    Aineq[9,16] = 1; Aineq[9,15] = -1;
    Aineq[10,19] = 1; Aineq[10,20] = -1;
    Aineq[11,23] = 1; Aineq[11,17] = -1;Aineq[11,28] = 1;
    Aineq[12,21] = -1; Aineq[12,22] = 1;
    Aineq = Aineq[1:, 1:] # convert 1-index to 0-index
    Aineq = -1 * Aineq # because in standarized formulation, it's Ax<=b but in our paper it is Ax>=b

#    if Label_scalers == None: # if flux in their true range instead of scaled range
#        Aineq = numpy.vstack([Aineq, -numpy.eye(29), numpy.eye(29)]) # add eye matrixes for Lbs and Ubs

    if not Aineq_bound is None :
        Aineq = numpy.vstack([Aineq, Aineq_bound])
    else:
        Aineq = numpy.matrix(Aineq)


    bineq = numpy.zeros((12+1, 1+1))
    bineq[2,1]= 100 * Substrates[Substrate2Index["fructose"]]
    bineq[6,1]= 100 * Substrates[Substrate2Index["pyruvate"]]
    bineq[10,1] = 100 * Substrates[Substrate2Index["glutamate"]]
    bineq = bineq[1:, 1:] # convert 1-index to 0-index

#    if Label_scalers == None: # if flux in their true range instead of scaled range
#        bineq = numpy.vstack([bineq, -Lbs, Ubs])
    if not Bineq_bound is None:
        bineq = numpy.vstack([bineq, Bineq_bound])
    else:
        bineq = numpy.matrix(bineq)

    Aeq = numpy.zeros((10+1, 29+1))
    Aeq[1,1] = 1;
    Aeq[2,3] = 1; Aeq[2,4] = -1;
    Aeq[3,11] = 1; Aeq[3,12] = -1; Aeq[3,13] = -1;
    Aeq[4,14] = 1; Aeq[4,16] = -1;
    Aeq[5,10] = 1; Aeq[5,11] = -1; Aeq[5,25] = -1;
    Aeq[6,18] = 1; Aeq[6,17] = -1;
    Aeq[7,15] = 1; Aeq[7,12] = -1; Aeq[7,14] = 1;
    Aeq[8,24] = 1; Aeq[8,18] = -1; Aeq[8,19] = 1;
    Aeq[9,22] = -1; Aeq[9,23] = 1; Aeq[9,24] = -1; Aeq[9,29] = 1;
    Aeq[10,20] = 1; Aeq[10,24] = 1;Aeq[10,21] = -1;
    Aeq = Aeq[1:, 1:] # convert 1-index to 0-index
    Aeq = numpy.matrix(Aeq)
#    Aeq = Aeq.transpose().tolist()

    beq = numpy.zeros((10+1,1+1))
    beq[1,1] = 100 * (Substrates[Substrate2Index["glucose"]] + Substrates[Substrate2Index["galactose"]])
    beq[2,1] = -100 * Substrates[Substrate2Index["glycerol"]]
    beq[5,1] = -100 * Substrates[Substrate2Index["gluconate"]]
    beq[6,1] = 100 * Substrates[Substrate2Index["citrate"]]
    beq[7,1] = 100 * Substrates[Substrate2Index["xylose"]]
    beq[9,1] = 100 * Substrates[Substrate2Index["malate"]]
    beq[10,1]= -100 * Substrates[Substrate2Index["succinate"]]
    beq = beq[1:, 1:] # convert 1-index to 0-index
    beq = numpy.matrix(beq)

    if Label_scalers is None:
        P = numpy.eye((29))
        q = [[Fluxes[i] for i in range(1, 29+1)]]
    else: # convert non-scaled fluxes into [0,1]
        P = numpy.square(numpy.diag([Label_scalers[i].scale_[0] for i in range(1, 29+1)]))
        q = [[Label_scalers[i].scale_**2 * Fluxes[i] for i in range(1, 29+1)]]
        if Debug:
            for i in range(1,29+1):
                pass

    q = -1*numpy.array(q).transpose() # -1 is because -v_i but f.T*x in standard quadprog formalization

#    print (list(map(numpy.shape, [Aineq, bineq, Aeq, beq, P, q])))

    q = q.ravel().reshape(-1, 1) # line added 2022-7-1

    [Aineq, bineq, Aeq, beq, P, q] = map(cvxopt.matrix, [Aineq, bineq, Aeq, beq, P, q])

    cvxopt.solvers.options['show_progress'] = False

    Solv = cvxopt.solvers.qp(P, q, Aineq, bineq, Aeq, beq)

    Solution = Solv['x']

    Solution = numpy.array(Solution)[:,0] # conversion from cvxopt's matrix to numpy array

    if Debug:

        numpy.set_printoptions(precision=4, suppress=True)

        pushLastWords("<pre>")
        pushLastWords(("".join([" V", "   Adjusted ", " Predicted ", "   Diff  ",  "  Diff%  ", " Diff%Rg   "]) ))
        for Idx, Value in enumerate(Solution):
            Diff =  Value-Fluxes[Idx+1]
            pushLastWords(("{0:2d}{1:10.3f}{2:10.3f}{3:10.3f}{4:8.1f}{5:8.1f}".\
                  format(Idx+1, Value, Fluxes[Idx+1], Diff, Diff/Fluxes[Idx+1]*100,  Diff/((Ubs-Lbs)[Idx][0])*100) )) # convert from 0-index to 1-index
        pushLastWords("</pre>")

    Solution = {i+1: Solution[i] for i in range(29)} # turn from numpy array to dict

    return Solution

def test(S):
    print (S)

def print_influxes(Influxes, pushLastWords):
    """Print influxes

    Influxes: dict, keys are influx id, values are floats
    """

    import sys
    sys.stderr = sys.stdout

#    print Influxes
    pushLastWords("""\
    <h2>Influx values based on given parameters:</h2>
    """)# % len(Vector)  #"\t".join(map(str, Vector))

    pushLastWords("""\
    <table border=0 border-spacing=5px>
      <tr>
       <td>

    """)

#    for x in range(5):
#        print x

    for ID, Value in Influxes.items():
        pushLastWords("""\
        v%s = %.4f, <br>
        """ % (ID, Value))

    pushLastWords ("</td><td> <img src=\"https://mflux.cs.iastate.edu/static/centralflux.png\">  </td>        </tr>      </table>")

#    for ID, Value in Influxes.iteritems():
#        print """\
#        v%s = %.4f, <br>
#        """ % (ID, Value)

def populate_boundary_inequalities(Boundary_dict, Debug=False):
    """
    Boundary_dict: Upper boundaries and lower boundaries for 29 fluxes, depending on user inputs,
                   e.g., {"lb29":999, "ub8":50}, populate ub and lb inequalities from them
    Aineq: X-by-29 binary matrix, where N is the number of Ubs and Lbs set by user
    Bineq: X-by-1 column vector
    for any v_j <= p, there is Aineq[i][j] ==  1 and Bineq[j] ==  P
    for any v_j >= p, there is Aineq[i][j] == -1 and Bineq[j] == -p
    Note the inequalities are: Ax <= B
    """
    if Boundary_dict == {}:
        return None, None

    Row_vectors  = [] # must be 29 columns and X rows where X is the number of Ubs and Lbs set by user
    Boundary_column_vectors = [] # X rows and 1 column
    for Polarity_Id, Bound_value in Boundary_dict.items():
        Bound_type, Flux_ID = Polarity_Id[:2], int(Polarity_Id[2:])
        Row_vector = numpy.zeros(29)
        if Bound_type == "lb":
            Bound_value = -1*Bound_value
            Row_vector[Flux_ID-1] = -1.
        elif Bound_type == "ub":
            Row_vector[Flux_ID-1] = 1.
        else:
            print("wrong boundary")
        Row_vectors.append(Row_vector)
        Boundary_column_vectors.append(Bound_value)
#        print "<br>", Bound_type, Flux_ID, Bound_value

    Aineq = numpy.vstack(Row_vectors)
    Bineq = numpy.vstack(Boundary_column_vectors)

    if Debug:
        print("<pre>")
        print(Aineq)
        print(Bineq)
        print("</pre>")

    return Aineq, Bineq

def process_boundaries(request, Substrates):
    """Extract boundaries for fluxes from user input
    Form: cgi object
    Features: {}, empty dictionary by default

    Notes
    =======
    In Substrates, the mapping from keys to real chemicals is as follows:
        1. Glucose
        2. Fructose
        3. Galactose
        4. Gluconate
        5. Glutamate
        6. Citrate
        7. Xylose
        8. Succinate
        9. Malate
        10. Lactate
        11. Pyruvate
        12. Glycerol
        13. Acetate
        14. NaHCO3

    """
    Substrate2Index= {"glucose":1, "galactose":3, "fructose":2, "gluconate":4, "glutamate":5, "citrate":6, "xylose":7, "succinate":8, "malate":9, "lactate":10, "pyruvate":11, "glycerol":12, "acetate":13}
    Feature_names = ["".join([Bound, ID]) for  (Bound, ID) in itertools.product(["lb", "ub"], list(map(str, list(range(1, 29+1))))) ]

    Features= {}
    for Feature_name in Feature_names:
        Feature_value = request.values.get(Feature_name, 0)
        if Feature_value:
#            print Feature_name, Feature_value
            Feature_value = html.escape(Feature_value)
            Features[Feature_name] = float(Feature_value) # convert all string to numbers

    if Substrates[Substrate2Index["acetate"]] == 0:
        Features["lb9"] = 0
    if Substrates[Substrate2Index["lactate"]] == 0:
        Features["lb27"] = 0

#   for Feature_name in Feature_names:
#       print """\
#       %s is %s,
#       """ % (Feature_name, Features[Feature_name])

    return Features

def process_input(Features, pushLastWords):
    """Process the result from CGI parsing to form feature vector including substrate matrixi
    Substrates: OrderedDict, keys as integers and values as floats
        1. Glucose
        2. Fructose
        3. Galactose
        4. Gluconate
        5. Glutamate
        6. Citrate
        7. Xylose
        8. Succinate
        9. Malate
        10. Lactate
        11. Pyruvate
        12. Glycerol
        13. Acetate
        14. NaHCO3

    Feature vectors order: [Species, Reactor, Nutrient, Oxygen, Method, MFA, Energy, Growth_rate, Substrate_uptake_rate] + ratio of 14 carbon sources in the order above
    """

    Num_substrates = 14 # excluding other carbon
    # Generate substrate matrix

    Substrates = collections.OrderedDict([(i,0) for i in range(1, Num_substrates+1)]) # substrate values, initialization
    Substrates[int(Features["Substrate_first"])] += Features["Ratio_first"]
    Substrates[int(Features["Substrate_sec"])] += Features["Ratio_sec"]

    # Form the feature vector
    Vector = [Features[Feature_name] for Feature_name in ["Species", "Reactor", "Nutrient", "Oxygen", "Method", "MFA", "Energy", "Growth_rate", "Substrate_uptake_rate"]]
    Vector += [Substrates[i] for i in range(1, Num_substrates+1)]
    Vector.append(Features["Substrate_other"]) # Other carbon source

    # Print input check
    try:
        import clp
        DB = clp.process_species_db("SI_1_species_db.csv")
        P  = clp.species_db_to_constraints(DB)
        if not clp.input_ok(P, Vector):
            pushLastWords("<p><font color=\"red\">The input data might violate the oxygen, substrate uptake rate or carbon sources of the selected species. Therefore, the following prediction may not be biologically meaningful. Please check your inputs!</font></p>")
    except:
        pushLastWords("could not load SI_1_species_db.csv for input check")

    # Print debug info

    Substrate_names = ["glucose", "fructose", "galactose", "gluconate", "glutamate", "citrate", "xylose", "succinate", "malate", "lactate", "pyruvate", "glycerol", "acetate",  "NaHCO3"]
    Substrate_dict = collections.OrderedDict([(i+1,Name) for i, Name in enumerate(Substrate_names)])
#    print "<p>Feature Vector (pre-one-hot-encoding and pre-scaling):", Vector, "</br>"
#    print "in which the substrates ratios are:", [(Substrate_dict[Index],Ratio) for Index, Ratio in Substrates.iteritems()],
#    print "<br>Feature vector size is ", len(Vector), "</p>"

    return Vector, Substrates

def rule_adjust(Influxes, Substrates):
    """Adjust influxes values using rules
    """

    Substrate2Index= {"glucose":1, "galactose":3, "fructose":2, "gluconate":4, "glutamate":5, "citrate":6, "xylose":7, "succinate":8, "malate":9, "lactate":10, "pyruvate":11, "glycerol":12, "acetate":13}

    #Step 1: Compute dependent influxes
#    Influxes[1] = 100 * Substrates[Substrate2Index["glucose"]]
#    Influxes[13] = Influxes[11] - Influxes[12]
#    Influxes[16] = Influxes[14]
#    Influxes[25] = Influxes[10] - Influxes[11] + 100 * Substrates[Substrate2Index["gluconate"]]
#    Influxes[18] = Influxes[17] + 100 * Substrates[Substrate2Index["citrate"]]
#    Influxes[15] = Influxes[12] - Influxes[14] + 100 * Substrates[Substrate2Index["xylose"]]
#    Influxes[24] = Influxes[18] - Influxes[19]
#    Influxes[21] = Influxes[20] + Influxes[24] + 100 * Substrates[Substrate2Index["succinate"]]
#    Influxes[22] = Influxes[21]
#    Influxes[29] = Influxes[22] + Influxes[24] - Influxes[23] + 100 * Substrates[Substrate2Index["malate"]]

    # Step 2: Correct flux values
    if Substrates[Substrate2Index["acetate"]] != 0:
        Influxes[9] = -100 * Substrates[Substrate2Index["acetate"]]
    if Substrates[Substrate2Index["lactate"]] != 0:
        Influxes[27] = -100 * Substrates[Substrate2Index["lactate"]]

    return Influxes

def special_species(ID):
    """Print messages based on special species
    """
    Dict = {206: ("Rhodobacter sphaeroides", "Rhodobacter sphaeroides is a kind of purple bacteria that can obtain energy through photosynthesis. It can perform photoheterotrophic, photoautotrophic and chemoheterotrophic growth. It is also able to fix nitrogen and produce hydrogen. Its heterotrophic fluxomic features include: glucose metabolism shows high flux through ED pathway, TCA cycle, pyruvate shunt, and malic enzyme, while cell can perform simultaneous CO2 fixation and glucose catabolism.", ("http://jb.asm.org/content/194/2/274.full.pdf", "http://jb.asm.org/content/187/5/1581.full")),
            205: ("Dinoroseobacter shibae", # or Phaeobacter gallaeciensis
"This species belongs to the Rhodobacteraceae. It uses organic substrates as carbon sources and can generate energy from light. Glucose-grown cells catabolize the carbon source exclusively via the ED pathway, whereas glycolysis and the PP pathway are for anabolic purposes only. Pyruvate carboxylase is involved in CO2 assimilation and the TCA cycle is functional.", ("http://bmcmicrobiol.biomedcentral.com/articles/10.1186/1471-2180-9-209",)),
            204:("Rhodopseudomonas palustris", "Rhodopseudomonas palustris is a purple non-sulfur bacterium and can have four metabolisms: photoautotrophic, photoheterotrophic, chemoautotrophic and chemoheterotrophic. Under photoheterotrophic condition, acetate metabolism is via TCA cycle, highly active glyoxylate shunt and phosphoenolpyruvate carboxykinase, while the Calvin cycle can re-fix CO2 from acetate oxidation. Under photoheterotrophic condition, a nifA* mutant represses its Calvin cycle and produces hydrogen. Non-growing photoheterotrophic cell can increases hydrogen yield from acetate by shifting from the glyoxylate shunt to the TCA cycle.", ("http://www.pnas.org/content/107/26/11669.full", "http://www.jbc.org/content/289/4/1960.full",)),
            203: ("Synechocystis 6803", "This cyanobacterium can grow photoautotrophic and photoheterotrophic/photomixotrophic (with glucose) conditions. Its photoautotrophic metabolism shows high fluxes through the Calvin Cycle, glycolysis and malic enzyme. Its oxidative pentose phosphate pathway is active, but its TCA cycle is weak and carries minimal fluxes through the GABA shunt. The mutant can uptake xylose and has acetate overflow via the phosphoketolase pathway. Under photomixotrophic condition, cyanobacteria can simultaneously use glucose and CO2. Under photoheterotrophic condition (PSII inactivation), it uses oxidative pentose phosphate pathway to generate NADPH from glucose.", ("http://pcp.oxfordjournals.org/content/55/9/1605.long", "http://www.sciencedirect.com/science/article/pii/S1096717611000887", "http://www.nature.com/articles/nplants201553", "http://jb.asm.org/content/197/5/943.long")),
            202:("Chlorobaculum tepidum", "This green sulfur bacterial species uses a reversed TCA cycle for CO2 fixation. It can also perform photomixotrophic metabolism using acetate and pyruvate.", ("http://www.jbc.org/content/285/50/39544.short",)),
            201:("Cyanothece 51142", "This cyanobacterium can fix nitrogen and perform photomixtrophic metabolism using glycerol. It has a broken TCA cycle. The nitrate-deficient condition limits CO2 fixation flux.", ("http://link.springer.com/article/10.1007%2Fs11120-013-9911-5",))
}
    if ID == 207: # These two species are the same
        ID = 205

    (Name, Description, URLs) = Dict[ID]
    print("<p><font color=\"red\">The species you selected is special:</font> %s</p>" % Description)
    print("<P>See also:<ul>")
    for URL in URLs:
        print("<li>%s</li>" % URL)
    print("</ul></p>")
    return None

def predict(Vector, Substrates, Boundary_dict, pushLastWords):
    """ Predict and adjust all influx values
    Vector: 1-D list of floats, the feature vector, including substrate matrix, size = 24
    Substrates: dict of floats, 1-indexed part of Feature_vector, ratio of substrates
    Boundary_dict: Upper boundaries and lower boundaries for 29 fluxes, depending on user inputs,
                   e.g., {"lb29":999, "ub8":50}, populate ub and lb inequalities from them
                   If no boundary set by user, it can be an empty dictionary
    Models: dict of models, 1-indexed, 29 moddels for 29 influxes.
    Calls adjust_influxes() to compute dependent influxes.
    """

    # special species
    if Vector[0] > 200:
        special_species(Vector[0])
        return None

    Models = pickle.load(open("models_svm.p", "rb"))
    Feature_scalers = pickle.load(open("feature_scalers.p", "rb"))
    Encoders = pickle.load(open("encoders.p", "rb"))
    Label_scalers = pickle.load(open("label_scalers.p", "rb"))

#    print "<p>Models, feature and label Scalers and one-hot Encoder loaded..</p>"
    #  Models: dict, keys are influx indexes and values are regression models

    T = time.time()
    Influxes = {}
#    Influxes = {Iundex:Model.predict(Scalers[Index].transform(Vector))[0] for Index, Model in Models.iteritems()}# use dictionary because influx IDs are not consecutive

#    print "Standardized (zero mean and unit variance) influx prediction from ML:"
    for vID, Model in Models.items():
        Vector_local = list(Vector) # make a copy; o/w Vector will be changed in one-hot encoding and standarization for different models
        categorical_features = [Vector[:6+1]]
        One_hot_encoding_of_categorical_features =  Encoders[vID].transform(categorical_features).toarray().tolist()[0]  # one-hot encoding for categorical features
        Vector_local =  One_hot_encoding_of_categorical_features + Vector_local[6+1:] # combine one-hot-encoded categorical features with continuous features (including substrate matrix)
        Vector_local = Feature_scalers[vID].transform([Vector_local]) # standarization of features
#        print Vector_local
        Influx_local = Model.predict(Vector_local) # prediction
        Influx_local = Label_scalers[vID].inverse_transform([Influx_local])
        Influxes[vID] = Influx_local[0][0]  # double index added 2022-7-1


    Influxes = quadprog_adjust(Substrates, Influxes, Boundary_dict, pushLastWords, Label_scalers=Label_scalers, Debug=True)
    Influxes = rule_adjust(Influxes, Substrates)

    T = time.time() -T

    print_influxes(Influxes, pushLastWords)

    pushLastWords("""</p>\
    <p>Using RBF kernel SVM as regressor. Parameters vary for different fluxes. For details, refer to <a href="https://mflux.cs.iastate.edu/static/svr_both_rbf_shuffle.log">this document generated by grid search on SVM parameters</a>. </p>
    <p>Standardization and Regression done in %.5f seconds.</p>
    """ % T)
    return Influxes
