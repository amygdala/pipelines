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

def automl_eval_tables_model(
	gcp_project_id: str,
	gcp_region: str,
  model_display_name: str,
  bucket_name: str,
  gcs_path: str,
  api_endpoint: str = None,
) -> NamedTuple('Outputs', [('evals_path', str), ('feat_list', str)]):
  import subprocess
  import sys
  subprocess.run([sys.executable, '-m', 'pip', 'install', 'googleapis-common-protos==1.6.0',
     '--no-warn-script-location'], env={'PIP_DISABLE_PIP_VERSION_CHECK': '1'}, check=True)
  subprocess.run([sys.executable, '-m', 'pip', 'install', 'google-cloud-automl==0.9.0',
     '--no-warn-script-location'], env={'PIP_DISABLE_PIP_VERSION_CHECK': '1'}, check=True)
  subprocess.run([sys.executable, '-m', 'pip', 'install', 'google-cloud-storage',
     '--no-warn-script-location'], env={'PIP_DISABLE_PIP_VERSION_CHECK': '1'}, check=True)


  import google
  import json
  import logging
  import pickle

  # import kfp
  from google.api_core.client_options import ClientOptions
  from google.api_core import exceptions
  from google.cloud import automl_v1beta1 as automl
  from google.cloud.automl_v1beta1 import enums
  from google.cloud import storage


  def copy_string_to_gcs(project, bucket_name, gcs_path, pstring):
    logging.info('Using bucket {} and path {}'.format(bucket_name, gcs_path))
    storage_client = storage.Client(project=project)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(pstring)


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

  # response = client.list_model_evaluations(model_display_name=model_display_name)
  # for evaluation in response:
  #   print("Model evaluation name: {}".format(evaluation.name))
  #   print("Model evaluation id: {}".format(evaluation.name.split("/")[-1]))
  #   print('disp name: {}'.format(evaluation.display_name))
  #   print('eval:-------\n{}'.format(evaluation))


  evals = list(client.list_model_evaluations(model_display_name=model_display_name))
  # with open('temp_oput2', "w") as f:
    # f.write('Model evals:\n{}'.format(evals))
  pstring = pickle.dumps(evals)
  # pstring = pickled_eval.hex()
  copy_string_to_gcs(gcp_project_id, bucket_name, gcs_path, pstring)
  # use bytes.fromhex(string) in other components, then pickle.loads() the result
  # xxx = bytes.fromhex(pstring)
  # reconst = pickle.loads(xxx)

  feat_list_string = json.dumps(feat_list)
  return(gcs_path, feat_list_string)


if __name__ == '__main__':
	import kfp
	kfp.components.func_to_container_op(automl_eval_tables_model,
      output_component_file='tables_eval_component.yaml', base_image='python:3.7')

# if __name__ == '__main__':

#   (eval_hex, features) = automl_eval_tables_model('aju-vtests2', 'us-central1', model_display_name='somodel_1579284627')
#   with open('temp_oput', "w") as f:
#     f.write(eval_hex)

