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

# An example of how the model eval info could be used to make decisions aboiut whether or not
# to deploy the model.
def automl_eval_threshold(
	gcp_project_id: str,
	gcp_region: str,
  model_display_name: str,
  bucket_name: str,
  gcs_path: str,
  api_endpoint: str = None,
  # eval_info_string: str = None,
  thresholds: str = '{"au_prc": 0.9}',
  confidence_threshold: float = 0.5

) -> NamedTuple('Outputs', [('deploy', bool)]):
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
  from google.api_core.client_options import ClientOptions
  from google.api_core import exceptions
  from google.cloud import automl_v1beta1 as automl
  from google.cloud.automl_v1beta1 import enums
  from google.cloud import storage


  def get_string_from_gcs(project, bucket_name, gcs_path):
    logging.info('Using bucket {} and path {}'.format(bucket_name, gcs_path))
    storage_client = storage.Client(project=project)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    return blob.download_as_string()

  logging.getLogger().setLevel(logging.INFO)  # TODO: make level configurable
  # TODO: we could instead check for region 'eu' and use 'eu-automl.googleapis.com:443'endpoint
  # in that case, instead of requiring endpoint to be specified.
  if api_endpoint:
    client_options = ClientOptions(api_endpoint=api_endpoint)
    client = automl.TablesClient(project=gcp_project_id, region=gcp_region,
        client_options=client_options)
  else:
    client = automl.TablesClient(project=gcp_project_id, region=gcp_region)

  thresholds_dict = json.loads(thresholds)
  logging.info('thresholds dict: {}'.format(thresholds_dict))

  try:
    eresults = {}
    # TODO: add handling of regression metrics..., confusion matrix stuff for binary classif case..
    eval_string = get_string_from_gcs(gcp_project_id, bucket_name, gcs_path)
    eval_info = pickle.loads(eval_string)
    multiclass = True  # aju temp testing
    # TODO:
    # Figure out what kind of eval it is...

    if multiclass and thresholds_dict:
      example_count = eval_info[0].evaluated_example_count
      print('Looking for example_count {}'.format(example_count))
      for e in eval_info[1:]:  # we know we don't want the first elt
        if e.evaluated_example_count == example_count:
          # print('found relevant eval {}'.format(e))
          # TODO: which position threshold ?
          eresults['au_prc'] = e.classification_evaluation_metrics.au_prc
          eresults['au_roc'] = e.classification_evaluation_metrics.au_roc
          eresults['log_loss'] = e.classification_evaluation_metrics.log_loss
          for i in e.classification_evaluation_metrics.confidence_metrics_entry:
            if i.confidence_threshold >= confidence_threshold:
              eresults['recall'] = i.recall
              eresults['precision'] = i.precision
              eresults['f1_score'] = i.f1_score
              break
          break
      logging.info('eresults: {}'.format(eresults))
      for k,v in thresholds_dict.items():
        logging.info('k {}, v {}'.format(k, v))
        if k == 'log_loss':
          if eresults[k] > v:
            logging.info('{} > {}; returning False'.format(
                eresults[k], v))
            return False
        else:
          if eresults[k] < v:
            logging.info('{} < {}; returning False'.format(
                eresults[k], v))
            return False
      return True
    else:
      return True
    # Get the confidence_metrics_entry with given confidence threshold
    # Grab the metrics and compare with those in 'thresholds'
    return True  # temp..
  except Exception as e:
    logging.warning(e)
    return True
  # If can't reconstruct the eval, or don't have thresholds defined,
  # return True as a signal to deploy.
  # TODO: is this the right default?



if __name__ == '__main__':
	import kfp
	kfp.components.func_to_container_op(automl_eval_threshold,
      output_component_file='tables_eval_thresh_component.yaml', base_image='python:3.7')


# if __name__ == "__main__":
#   automl_eval_threshold('aju-vtests2', 'us-central1',
#       model_display_name='amy_test3_20191219032001')
