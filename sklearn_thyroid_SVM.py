from __future__ import print_function

import time
import sys
from io import StringIO
import io
import os
import shutil
import boto3


import argparse
import csv
import json
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn import preprocessing
from sklearn.metrics.pairwise import rbf_kernel, polynomial_kernel, linear_kernel, sigmoid_kernel
from sklearn import svm
from sklearn.externals import joblib
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Binarizer, StandardScaler, OneHotEncoder
from sagemaker_containers.beta.framework import (
    content_types, encoders, env, modules, transformer, worker)


feature_columns_names = [
    'on_thyroxine',
    'query_on_thyroxine',
    'on_antithyroid_medication',
    'thyroid_surgery',
    'query_hypothyroid',
    'query_hyperthyroid',
    'pregnant',
    'sick',
    'tumor',
    'lithium',
    'goitre',
    'TSH_measured',
    'T3_measured',
    'TT4_measured',
    'T4U_measured',
    'FTI_measured',
    'age',
    'sex',
    'TSH',
    'T3',
    'TT4',
    'T4U',
    'FTI']

feature_columns_dtype = {
    'on_thyroxine': np.float32,
    'query_on_thyroxine': np.float32,
    'on_antithyroid_medication': np.float32,
    'thyroid_surgery': np.float32,
    'query_hypothyroid': np.float32,
    'query_hyperthyroid': np.float32,
    'pregnant': np.float32,
    'sick': np.float32,
    'tumor': np.float32,
    'lithium': np.float32,
    'goitre': np.float32,
    'TSH_measured': np.float32,
    'T3_measured': np.float32,
    'TT4_measured': np.float32,
    'T4U_measured': np.float32,
    'FTI_measured': np.float32,
    'age': np.float32,
    'sex': np.float32,
    'TSH': np.float32,
    'T3': np.float32,
    'TT4': np.float32,
    'T4U': np.float32,
    'FTI': np.float32}

label_column = 'classes'
label_column_dtype = {'classes': np.float64}

def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z
    
def my_kernel(X , K):
    # Creating the RBF kernel
    RBFKernel= rbf_kernel(X, K)
    RBFKernel= RBFKernel.astype(np.double)

    linearKernel = linear_kernel(X,K)
    linearKernel = linearKernel.astype(np.double)

    return (RBFKernel + linearKernel)/2

def model():
    return 

if __name__ == '__main__' :
    parser = argparse.ArgumentParser()

    # Sagemaker specific arguments. Defaults are set in the environment variables.
    parser.add_argument('--output-data-dir', type=str, default=os.environ['SM_OUTPUT_DATA_DIR'])
    parser.add_argument('--model-dir', type=str, default=os.environ['SM_MODEL_DIR'])
    parser.add_argument('--train', type=str, default=os.environ['SM_CHANNEL_TRAIN'])

    args = parser.parse_args()
    
	# Take the set of files and read them all into a single pandas dataframe
    input_files = [ os.path.join(args.train, file) for file in os.listdir(args.train) ]

    raw_data = [ pd.read_csv(
        file, 
        header=None, 
        names=feature_columns_names + [label_column],
        dtype=merge_two_dicts(feature_columns_dtype, label_column_dtype)) for file in input_files ]

    concat_data = pd.concat(raw_data)
    
    features = concat_data.iloc[:, 0:-1]
    target = concat_data.iloc[:, -1]

    scaler = preprocessing.StandardScaler().fit(features)
    X = scaler.transform(features)
    clf = svm.SVC(kernel='linear')
    clf.fit(X,target)
    joblib.dump(clf, os.path.join(args.model_dir, "model-SVM-preprocessed.joblib"))
    print("saved model!")
    

def input_fn(input_data, content_type):
    """Parse input data payload

    We currently only take csv input. Since we need to process both labelled
    and unlabelled data we first determine whether the label column is present
    by looking at how many columns were provided.
    """
    csv = io.BytesIO(input_data)
    value = csv.getvalue().decode().rstrip()
    df = np.fromstring(value, dtype=float, sep=',')
    return df

def output_fn(prediction, accept):
    """Format prediction output

    The default accept/content-type between containers for serial inference is JSON.
    We also want to set the ContentType or mimetype as the same value as accept so the next
    container can read the response payload correctly.
    """
    if accept == "application/json":
        instances = []
        for row in prediction.tolist():
            instances.append({"features": row})

        json_output = {"instances": instances}

        return worker.Response(json.dumps(json_output), accept, mimetype=accept)
    elif accept == 'text/csv':
        return worker.Response(encoders.encode(prediction, accept), accept, mimetype=accept)
    else:
        raise RuntimeException("{} accept type is not supported by this script.".format(accept))

def predict_fn(input_data, model):
    """Preprocess input data

    We implement this because the default predict_fn uses .predict(), but our model is a preprocessor
    so we want to use .transform().

    The output is returned in the following order:

        rest of features either one hot encoded or standardized
    """
    re = input_data.reshape(1,23)
    features = model.predict(re)
    
    if label_column in input_data:
        # Return the label (as the first column) and the set of features.
        return np.insert(features, 0, input_data[label_column], axis=1)
    else:
        # Return only the set of features
        return features
        
def model_fn(model_dir):
    """Deserialize fitted model
    """
    preprocessor = joblib.load(os.path.join(model_dir, "model-SVM-preprocessed.joblib"))
    return preprocessor