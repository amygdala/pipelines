# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import NamedTuple
import time


def automl_eval_tables_model(
	gcp_project_id: str,
	gcp_region: str,
	# dataset_display_name: str,
  model_display_name: str,
  api_endpoint: str = None,
) -> NamedTuple('Outputs', [('evals', str), ('feat_list', str)]):
  import google
  import json
  import logging
  import pickle
  from google.api_core.client_options import ClientOptions
  from google.api_core import exceptions
  from google.cloud import automl_v1beta1 as automl
  from google.cloud.automl_v1beta1 import enums
  import subprocess
  import sys


  def get_model_details(client, model_display_name):
    try:
        model = client.get_model(model_display_name=model_display_name)
    except exceptions.NotFound:
        logging.info("Model %s not found." % model_display_name)
        return (None, None)

    model = client.get_model(model_display_name=model_display_name)
    # Retrieve deployment state.
    if model.deployment_state == enums.Model.DeploymentState.DEPLOYED:
        deployment_state = "deployed"
    else:
        deployment_state = "undeployed"
    # get features of top global importance
    feat_list = [
        (column.feature_importance, column.column_display_name)
        for column in model.tables_model_metadata.tables_model_column_info
    ]
    feat_list.sort(reverse=True)
    if len(feat_list) < 10:
        feat_to_show = len(feat_list)
    else:
        feat_to_show = 10

    # Display the model information.
    logging.info("Model name: {}".format(model.name))
    logging.info("Model id: {}".format(model.name.split("/")[-1]))
    logging.info("Model display name: {}".format(model.display_name))
    logging.info("Features of top importance:")
    for feat in feat_list[:feat_to_show]:
        logging.info(feat)
    logging.info("Model create time:")
    logging.info("\tseconds: {}".format(model.create_time.seconds))
    logging.info("\tnanos: {}".format(model.create_time.nanos))
    logging.info("Model deployment state: {}".format(deployment_state))

    return (model, feat_list)

  subprocess.run([sys.executable, '-m', 'pip', 'install', 'google-cloud-automl==0.9.0', '--quiet', '--no-warn-script-location'], env={'PIP_DISABLE_PIP_VERSION_CHECK': '1'}, check=True)

  logging.getLogger().setLevel(logging.INFO)  # TODO: make level configurable
  # TODO: we could instead check for region 'eu' and use 'eu-automl.googleapis.com:443'endpoint
  # in that case, instead of requiring endpoint to be specified.
  if api_endpoint:
    client_options = ClientOptions(api_endpoint=api_endpoint)
    client = automl.TablesClient(project=gcp_project_id, region=gcp_region,
        client_options=client_options)
  else:
    client = automl.TablesClient(project=gcp_project_id, region=gcp_region)

  (model, feat_list) = get_model_details(client, model_display_name)

  evals = list(client.list_model_evaluations(model_display_name=model_display_name))
  logging.info('Model evals: {}'.format(evals))
  pickled_eval = pickle.dumps(evals[1])
  # reconst = pickle.loads(pickled_eval)
  # print('reconst:')
  # print(reconst)
  return(pickled_eval, json.dumps(feat_list))



# if __name__ == '__main__':
# 	import kfp
# 	kfp.components.func_to_container_op(automl_eval_tables_model, output_component_file='tables_eval_component.yaml', base_image='python:3.7')


if __name__ == "__main__":
  automl_eval_tables_model('aju-vtests2', 'us-central1', model_display_name='amy_test3_20191219032001')
