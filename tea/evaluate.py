from tea.ast import *
from tea.dataset import Dataset
from tea.evaluate_data_structures import VarData, BivariateData, MultivariateData # runtime data structures
from tea.evaluate_result_data_structures import ResultData
from tea.evaluate_helper_methods import determine_study_type, assign_roles, add_paired_property, compute_data_properties, compute_combined_data_properties, execute_test
from .solver import synthesize_tests
# from tea.solver import find_applicable_bivariate_tests

import attr
from typing import Any
from types import SimpleNamespace # allows for dot notation access for dictionaries

from scipy import stats # Stats library used
import statsmodels.api as sm
import statsmodels.formula.api as smf
import numpy as np # Use some stats from numpy instead
import pandas as pd
# import bootstrapped as bs

# TODO: Pass participant_id as part of experimental design, not load_data
def evaluate(dataset: Dataset, expr: Node, assumptions: Dict[str, str], design: Dict[str, str]=None):
    if isinstance(expr, Variable):
        # dataframe = dataset[expr.name] # I don't know if we want this. We may want to just store query (in metadata?) and
        # then use query to get raw data later....(for user, not interpreter?)
        metadata = dataset.get_variable_data(expr.name) # (dtype, categories)
        # if expr.name == 'strategy':
        #     import pdb; pdb.set_trace()
        metadata['var_name'] = expr.name
        metadata['query'] = ''
        return VarData(metadata)

    elif isinstance(expr, Literal):
        data = pd.Series([expr.value] * len(dataset.data), index=dataset.data.index) # Series filled with literal value
        # metadata = None # metadata=None means literal
        metadata = dict() # metadata=None means literal
        metadata['var_name'] = '' # because not a var in the dataset 
        metadata['query'] = ''
        metadata['value'] = expr.value
        return VarData(data, metadata)

    elif isinstance(expr, Equal):
        lhs = evaluate(dataset, expr.lhs)
        rhs = evaluate(dataset, expr.rhs)
        assert isinstance(lhs, VarData)
        assert isinstance(rhs, VarData)
        
        
        dataframe = lhs.dataframe[lhs.dataframe == rhs.dataframe]
        metadata = lhs.metadata
        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = f" == \'{rhs.metadata['value']}\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" == {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")
        
        return VarData(metadata)

    elif isinstance(expr, NotEqual): 
        rhs = evaluate(dataset, expr.rhs)
        lhs = evaluate(dataset, expr.lhs)
        assert isinstance(rhs, VarData)
        assert isinstance(lhs, VarData)
        
        dataframe = lhs.dataframe[lhs.dataframe != rhs.dataframe]
        metadata = lhs.metadata
        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = " != \'\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" != {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")
        return VarData(metadata)

    elif isinstance(expr, LessThan):
        lhs = evaluate(dataset, expr.lhs)
        rhs = evaluate(dataset, expr.rhs)
        assert isinstance(lhs, VarData)
        assert isinstance(rhs, VarData)

        dataframe = None
        metadata = rhs.metadata
        
        if (not lhs.metadata):
            raise ValueError('Malformed Relation. Filter on Variables must have variable as rhs')
        elif (lhs.metadata['dtype'] is DataType.NOMINAL):
            raise ValueError('Cannot compare nominal values with Less Than')
        elif (lhs.metadata['dtype'] is DataType.ORDINAL):
            # TODO May want to add a case should RHS and LHS both be variables
            # assert (rhs.metadata is None) 
            comparison = rhs.dataframe.iloc[0]
            if (isinstance(comparison, str)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] < categories[comparison]]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name
                
            elif (np.issubdtype(comparison, np.integer)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] < comparison]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name                

            else: 
                raise ValueError(f"Cannot compare ORDINAL variables to {type(rhs.dataframe.iloc[0])}")


        elif (lhs.metadata['dtype'] is DataType.INTERVAL or lhs.metadata['dtype'] is DataType.RATIO):
            comparison = rhs.dataframe.iloc[0]
             # Get raw Pandas Series indices for desired data
            ids  = [i for i,x in enumerate(lhs.dataframe) if x < comparison]
            # Get Pandas Series set indices for desired data
            p_ids = [lhs.dataframe.index.values[i] for i in ids]
            # Create new Pandas Series with only the desired data, using set indices
            dataframe = pd.Series(lhs.dataframe, p_ids)
            dataframe.index.name = dataset.pid_col_name   

        else:
            raise Exception(f"Invalid Less Than Operation:{lhs} < {rhs}")

        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = " < \'\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" < {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")
        return VarData(metadata)

    elif isinstance(expr, LessThanEqual):
        lhs = evaluate(dataset, expr.lhs)
        rhs = evaluate(dataset, expr.rhs)
        assert isinstance(lhs, VarData)
        assert isinstance(rhs, VarData)


        dataframe = None
        metadata = rhs.metadata
        
        if (not lhs.metadata):
            raise ValueError('Malformed Relation. Filter on Variables must have variable as rhs')
        elif (lhs.metadata['dtype'] is DataType.NOMINAL):
            raise ValueError('Cannot compare nominal values with Less Than')
        elif (lhs.metadata['dtype'] is DataType.ORDINAL):
            # TODO May want to add a case should RHS and LHS both be variables
            # assert (rhs.metadata is None)
            comparison = rhs.dataframe.iloc[0]
            if (isinstance(comparison, str)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] <= categories[comparison]]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name
                
            elif (np.issubdtype(comparison, np.integer)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] <= comparison]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name                

            else: 
                raise ValueError(f"Cannot compare ORDINAL variables to {type(rhs.dataframe.iloc[0])}")


        elif (lhs.metadata['dtype'] is DataType.INTERVAL or lhs.metadata['dtype'] is DataType.RATIO):
            comparison = rhs.dataframe.iloc[0]
             # Get raw Pandas Series indices for desired data
            ids  = [i for i,x in enumerate(lhs.dataframe) if x <= comparison]
            # Get Pandas Series set indices for desired data
            p_ids = [lhs.dataframe.index.values[i] for i in ids]
            # Create new Pandas Series with only the desired data, using set indices
            dataframe = pd.Series(lhs.dataframe, p_ids)
            dataframe.index.name = dataset.pid_col_name   

        else:
            raise Exception(f"Invalid Less Than Equal Operation:{lhs} <= {rhs}")


        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = " <= \'\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" <= {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")

        return VarData(metadata)
    
    elif isinstance(expr, GreaterThan):
        lhs = evaluate(dataset, expr.lhs)
        rhs = evaluate(dataset, expr.rhs)
        assert isinstance(lhs, VarData)
        assert isinstance(rhs, VarData)


        dataframe = None
        metadata = rhs.metadata
        
        if (not lhs.metadata):
            raise ValueError('Malformed Relation. Filter on Variables must have variable as rhs')
        elif (lhs.metadata['dtype'] is DataType.NOMINAL):
            raise ValueError('Cannot compare nominal values with Greater Than')
        elif (lhs.metadata['dtype'] is DataType.ORDINAL):
            # TODO May want to add a case should RHS and LHS both be variables
            # assert (rhs.metadata is None) 
            comparison = rhs.dataframe.iloc[0]
            if (isinstance(comparison, str)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] > categories[comparison]]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name
                
            elif (np.issubdtype(comparison, np.integer)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] > comparison]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name                

            else: 
                raise ValueError(f"Cannot compare ORDINAL variables to {type(rhs.dataframe.iloc[0])}")


        elif (lhs.metadata['dtype'] is DataType.INTERVAL or lhs.metadata['dtype'] is DataType.RATIO):
            comparison = rhs.dataframe.iloc[0]
             # Get raw Pandas Series indices for desired data
            ids  = [i for i,x in enumerate(lhs.dataframe) if x > comparison]
            # Get Pandas Series set indices for desired data
            p_ids = [lhs.dataframe.index.values[i] for i in ids]
            # Create new Pandas Series with only the desired data, using set indices
            dataframe = pd.Series(lhs.dataframe, p_ids)
            dataframe.index.name = dataset.pid_col_name   

        else:
            raise Exception(f"Invalid Greater Than Operation:{lhs} > {rhs}")

        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = " > \'\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" > {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")

        return VarData(metadata) 
   
    elif isinstance(expr, GreaterThanEqual):
        lhs = evaluate(dataset, expr.lhs)
        rhs = evaluate(dataset, expr.rhs)
        assert isinstance(lhs, VarData)
        assert isinstance(rhs, VarData)


        dataframe = None
        metadata = rhs.metadata
        
        if (not lhs.metadata):
            raise ValueError('Malformed Relation. Filter on Variables must have variable as rhs')
        elif (lhs.metadata['dtype'] is DataType.NOMINAL):
            raise ValueError('Cannot compare nominal values with Greater Than Equal')
        elif (lhs.metadata['dtype'] is DataType.ORDINAL):
            # TODO May want to add a case should RHS and LHS both be variables
            # assert (rhs.metadata is None) 
            comparison = rhs.dataframe.iloc[0]
            if (isinstance(comparison, str)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] >= categories[comparison]]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name
                
            elif (np.issubdtype(comparison, np.integer)):
                categories = lhs.metadata['categories'] # OrderedDict
                # Get raw Pandas Series indices for desired data
                ids  = [i for i,x in enumerate(lhs.dataframe) if categories[x] >= comparison]
                # Get Pandas Series set indices for desired data
                p_ids = [lhs.dataframe.index.values[i] for i in ids]
                # Create new Pandas Series with only the desired data, using set indices
                dataframe = pd.Series(lhs.dataframe, p_ids)
                dataframe.index.name = dataset.pid_col_name                

            else: 
                raise ValueError(f"Cannot compare ORDINAL variables to {type(rhs.dataframe.iloc[0])}")


        elif (lhs.metadata['dtype'] is DataType.INTERVAL or lhs.metadata['dtype'] is DataType.RATIO):
            comparison = rhs.dataframe.iloc[0]
             # Get raw Pandas Series indices for desired data
            ids  = [i for i,x in enumerate(lhs.dataframe) if x >= comparison]
            # Get Pandas Series set indices for desired data
            p_ids = [lhs.dataframe.index.values[i] for i in ids]
            # Create new Pandas Series with only the desired data, using set indices
            dataframe = pd.Series(lhs.dataframe, p_ids)
            dataframe.index.name = dataset.pid_col_name   

        else:
            raise Exception(f"Invalid Greater Than Equal Operation:{lhs} >= {rhs}")


        if (isinstance(expr.rhs, Literal)):
            metadata['query'] = " >= \'\'" # override lhs metadata for query
        elif (isinstance(expr.rhs, Variable)): 
            metadata['query'] = f" >= {rhs.metadata['var_name']}"
        else: 
            raise ValueError(f"Not implemented for {rhs}")
        return VarData(metadata) 

    elif isinstance(expr, Relate):    
        vars = []

        for v in expr.vars: 
            eval_v = evaluate(dataset, v, design)    
            
            if not eval_v: 
                raise ValueError("The variables you are referencing are not defined as variables in your list of variables.")
            assert isinstance(eval_v, VarData)

            vars.append(eval_v)

        # What kind of study are we analyzing?
        study_type = determine_study_type(vars, design)

        # Assign roles to variables we are analyzing
        vars = assign_roles(vars, study_type, design)

        # Compute individual variable properties
        # vars = compute_data_properties(dap1ataset, vars) 
        
        combined_data = None
        # Do we have a Bivariate analysis?
        if len(vars) == 2: 
            combined_data = BivariateData(vars, study_type, alpha=float(assumptions['alpha'])) 
        else: # Do we have a Multivariate analysis?
            combined_data = MultivariateData(vars, study_type, alpha=float(assumptions['alpha']))
        
        # Add paired property
        add_paired_property(dataset, combined_data, study_type, design) # check sample sizes are identical
        # Compute between variable level properties
        # combined_data = compute_combined_data_properties(dataset, combined_data, study_type, design)

        # CEGIS-style synthesis
        # Synthesize tests
        tests = synthesize_tests(dataset, assumptions, combined_data)
        
        # import pdb; pdb.set_trace()
        """"
        # verify_properties(properties_and_tests)
        # get_tests
        # execute_tests
        # interpret_tests_results
        # print(tests)
        for test in tests:
            print("\nValid test: %s" % test.name)
            print("Properties:")
            properties = test.properties()
            for prop in properties:
                property_identifier = ""
                if prop.scope == "test":
                    property_identifier = test.name + ": " + prop.name
                else:
                    for var_indices in test.properties_for_vars[prop]:
                        for var_index in var_indices:
                            property_identifier += f"variable {test.test_vars[var_index].name} "
                        property_identifier += ": %s" % prop.name
                print(property_identifier)
        """
        
        # Execute and store results from each valid test
        results = {}
        if len(tests) == 0: 
            tests.append('bootstrap') # Default to bootstrap
            
        for test in tests: 
            test_result = execute_test(dataset, design, combined_data, test)
            results[test] = test_result
        
        if 'bootstrap' in tests: 
            # import pdb; pdb.set_trace()
            pass

        # TODO: Calculate effect size for experiments!!
        # calculate_effect_size()
        # import pdb; pdb.set_trace()
        
        # TODO One-sided test?
        if expr.predictions:
            # import pdb; pdb.set_trace()
            
            # T-tests: may greater-than test when p/2 < alpha and t > 0, and of a less-than test when p/2 < alpha and t < 0
            # --> may want to divide p-value in t-test (before return)

            # Add something to the results that they are one-sided vs two-sided tests? 

            # TODO For f_test/... post hoc comparisons depending on predictions
            pass
            
        return ResultData(results)

    elif isinstance(expr, Mean):
        var = evaluate(dataset, expr.var)
        assert isinstance(var, VarData)

        # bs.bootstrap(var.dataframe, stat_func=
        # bs_stats.mean)

        raise Exception('Not implemented Mean')