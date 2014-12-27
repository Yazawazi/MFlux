def test(S):
    print S

def print_influxes(Influxes):
    """Print influxes
    
    Influxes: dict, keys are influx id, values are floats
    """
#    print Influxes
    print """\
    <h2>Influx values based on given parameters:</h2>
    """# % len(Vector)  #"\t".join(map(str, Vector))

    for ID, Value in Influxes.iteritems():
        print """\
        v%s = %s, &nbsp; 
        """ % (ID, Value)

def process_input(Features):
    """Process the result from CGI parsing to form feature vector including substrate matrix
    """

    Num_substrates = 14 # excluding other carbon
    # Generate substrate matrix
    import collections
    Substrates = collections.OrderedDict([(i,0) for i in range(1, Num_substrates+1)]) # substrate values, initialization
    Substrates[int(Features["Substrate_first"])]= Features["Ratio_first"]
    Substrates[int(Features["Substrate_sec"])]= Features["Ratio_sec"]

    # Form the feature vector
    Vector = [Features[Feature_name] for Feature_name in ["Species", "Reactor", "Nutrient", "Oxygen", "Method", "MFA", "Energy", "Growth_rate", "Substrate_uptake_rate"]]
    Vector += [Substrates[i] for i in range(1, Num_substrates+1)]
    Vector.append(Features["Substrate_other"])

    # Print debug info

    Substrate_names = ["glucose", "fructose", "galactose", "gluconate", "glutamate", "citrate", "xylose", "succinate", "malate", "lactate", "pyruvate", "glycerol", "acetate",  "NaHCO3"]
    Substrate_dict = collections.OrderedDict([(i+1,Name) for i, Name in enumerate(Substrate_names)])
    print "<p>Feature Vector (prescaled):", Vector, "</p>"
    print "<p>in which the substrates ratios are:", [(Substrate_dict[Index],Ratio) for Index, Ratio in Substrates.iteritems()], "</p>"
    print "<p>Feature vector size is ", len(Vector), "</p>"

    return Vector, Substrates

def adjust_influxes(Influxes, Substrates):
    """Adjust influxes values
    """
    Substrate2Index= {"glucose":1, "galactose":3, "gluconate":4, "citrate":6, "xylose":7, "succinate":8, "malate":9, "lactate":10, "acetate":13}
 
    #Step 1: Compute dependent influxes 
    Influxes[1] = 100 * Substrates[Substrate2Index["glucose"]]
    Influxes[13] = Influxes[11] - Influxes[12]
    Influxes[16] = Influxes[14]
    Influxes[25] = Influxes[10] - Influxes[11] + 100 * Substrates[Substrate2Index["gluconate"]]
    Influxes[18] = Influxes[17] + 100 * Substrates[Substrate2Index["citrate"]]
    Influxes[15] = Influxes[12] - Influxes[14] + 100 * Substrates[Substrate2Index["xylose"]]
    Influxes[24] = Influxes[18] - Influxes[19]
    Influxes[21] = Influxes[20] + Influxes[24] + 100 * Substrates[Substrate2Index["succinate"]]
    Influxes[22] = Influxes[21]
    Influxes[29] = Influxes[22] + Influxes[24] - Influxes[23] + 100 * Substrates[Substrate2Index["malate"]]

    # Step 2: Correct flux values
    if Substrates[Substrate2Index["acetate"]] != 0:
        Influxes[9] = -100 * Substrates[Substrate2Index["acetate"]]
    if  Substrates[Substrate2Index["lactate"]] != 0:
        Influxes[27] = -100 * Substrates[Substrate2Index["lactate"]]

    return Influxes

def predict(Vector, Substrates):
    """ Predict and adjust all influx values

    Vector: list of floats, the feature vector, including substrate matrix, size = 24
    Substrates: dict of floats, 1-indexed part of Feature_vector, ratio of substrates
    Models: dict of models, 1-indexed, 29 moddels for 29 influxes. 
    """
    import cPickle
    import time
    import collections

    Models = cPickle.load(open("models_knn.p", "r"))
    Scalers = cPickle.load(open("scalers.p", "r"))
    print "Models and Scalers loaded" 
    #  Models: dict, keys are influx indexes and values are regression models

    T = time.clock()
    Influxes = {Index:Model.predict(Scalers[Index].transform(Vector))[0] for Index, Model in Models.iteritems()}# use dictionary because influx IDs are not consecutive
    Influxes = adjust_influxes(Influxes, Substrates)
    print_influxes(Influxes)

    T = time.clock() -T
    print """</p>\
    <p>Using a k-NN model where k=5, uniform weights for all neighbors, BallTree of leaf size 30 and Minkowski distance. </p>
    <p>Standarization and Regression done in %s seconds.</p>
    """ % T
    return Influxes 

