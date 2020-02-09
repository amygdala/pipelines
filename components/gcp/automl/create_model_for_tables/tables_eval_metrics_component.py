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
from kfp.components import InputPath, OutputPath


# An example of how the model eval info could be used to make decisions aboiut whether or not
# to deploy the model.
def automl_eval_metrics(
	gcp_project_id: str,
	gcp_region: str,
  model_display_name: str,
  bucket_name: str,
  # gcs_path: str,
  eval_data_path: InputPath('evals'),
  api_endpoint: str = None,
  # thresholds: str = '{"au_prc": 0.9}',
  thresholds: str = '{"mean_absolute_error": 450}',
  confidence_threshold: float = 0.5  # for classification

) -> NamedTuple('Outputs', [('deploy', bool)]):
  import subprocess
  import sys
  subprocess.run([sys.executable, '-m', 'pip', 'install', 'googleapis-common-protos==1.6.0',
      '--no-warn-script-location'], env={'PIP_DISABLE_PIP_VERSION_CHECK': '1'}, check=True)
  subprocess.run([sys.executable, '-m', 'pip', 'install', 'google-cloud-automl==0.9.0',
     'google-cloud-storage',
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


  # def get_string_from_gcs(project, bucket_name, gcs_path):
  #   logging.info('Using bucket {} and path {}'.format(bucket_name, gcs_path))
  #   storage_client = storage.Client(project=project)
  #   bucket = storage_client.get_bucket(bucket_name)
  #   blob = bucket.blob(gcs_path)
  #   return blob.download_as_string()

  # def upload_blob(bucket_name, source_file_name, destination_blob_name,
  #     public_url=False):
  #   """Uploads a file to the bucket."""

  #   storage_client = storage.Client()
  #   bucket = storage_client.bucket(bucket_name)
  #   blob = bucket.blob(destination_blob_name)

  #   blob.upload_from_filename(source_file_name)

  #   logging.info("File {} uploaded to {}.".format(
  #           source_file_name, destination_blob_name))
  #   if public_url:
  #     blob.make_public()
  #     logging.info("Blob {} is publicly accessible at {}".format(
  #             blob.name, blob.public_url))
  #   return blob.public_url

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

  def regression_threshold_check(eval_info):
    eresults = {}
    rmetrics = eval_info[1].regression_evaluation_metrics
    logging.info('got regression eval {}'.format(eval_info[1]))
    eresults['root_mean_squared_error'] = rmetrics.root_mean_squared_error
    eresults['mean_absolute_error'] = rmetrics.mean_absolute_error
    eresults['r_squared'] = rmetrics.r_squared
    eresults['mean_absolute_percentage_error'] = rmetrics.mean_absolute_percentage_error
    eresults['root_mean_squared_log_error'] = rmetrics.root_mean_squared_log_error
    for k,v in thresholds_dict.items():
      logging.info('k {}, v {}'.format(k, v))
      if k in ['root_mean_squared_error', 'mean_absolute_error', 'mean_absolute_percentage_error']:
        if eresults[k] > v:
          logging.info('{} > {}; returning False'.format(
              eresults[k], v))
          return (False, eresults)
      elif eresults[k] < v:
        logging.info('{} < {}; returning False'.format(
            eresults[k], v))
        return (False, eresults)
    return (True, eresults)

  def classif_threshold_check(eval_info):
    eresults = {}
    example_count = eval_info[0].evaluated_example_count
    print('Looking for example_count {}'.format(example_count))
    for e in eval_info[1:]:  # we know we don't want the first elt
      if e.evaluated_example_count == example_count:
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
          return (False, eresults)
      else:
        if eresults[k] < v:
          logging.info('{} < {}; returning False'.format(
              eresults[k], v))
          return (False, eresults)
    return (True, eresults)

  def generate_cm_metadata():
    pass

  # testing...
  with open(eval_data_path, 'rb') as f:
    logging.info('successfully opened eval_data_path {}'.format(eval_data_path))
    try:
      eval_info = pickle.loads(f.read())
      # TODO: add handling of confusion matrix stuff for binary classif case..
      # eval_string = get_string_from_gcs(gcp_project_id, bucket_name, gcs_path)
      # eval_info = pickle.loads(eval_string)

      classif = False
      binary_classif = False
      regression = False
      # TODO: ughh... what's the right way to figure out the model type?
      if eval_info[1].regression_evaluation_metrics and eval_info[1].regression_evaluation_metrics.root_mean_squared_error:
        regression=True
        logging.info('found regression metrics {}'.format(eval_info[1].regression_evaluation_metrics))
      elif eval_info[1].classification_evaluation_metrics and eval_info[1].classification_evaluation_metrics.au_prc:
        classif = True
        logging.info('found classification metrics {}'.format(eval_info[1].classification_evaluation_metrics))
        # TODO: detect binary classification case

      if regression and thresholds_dict:
        res, eresults = regression_threshold_check(eval_info)
        # logging.info('eresults: {}'.format(eresults))
        metadata = {
          'outputs' : [
          {
            'storage': 'inline',
            'source': '# Regression metrics:\n\n```{}```\n'.format(eresults),
            'type': 'markdown',
          }]}
        logging.info('using metadata dict {}'.format(json.dumps(metadata)))
        with open('/mlpipeline-ui-metadata.json', 'w') as f:
          json.dump(metadata, f)
        logging.info('deploy flag: {}'.format(res))
        # TODO: generate ui-metadata as appropriate
        return res

      elif classif and thresholds_dict:
        res, eresults = classif_threshold_check(eval_info)
        # logging.info('eresults: {}'.format(eresults))
        metadata = {
          'outputs' : [
          {
            'storage': 'inline',
            'source': '# classification metrics for confidence threshold {}:\n\n```{}```\n'.format(
                confidence_threshold, eresults),
            'type': 'markdown',
          }]}
        logging.info('using metadata dict {}'.format(json.dumps(metadata)))
        with open('/mlpipeline-ui-metadata.json', 'w') as f:
          json.dump(metadata, f)
        logging.info('deploy flag: {}'.format(res))
        # TODO: generate confusion matrix ui-metadata as approp etc.
        if binary_classif:
          generate_cm_metadata()
        return res
      else:
        return True
    except Exception as e:
      logging.warning(e)
      # If can't reconstruct the eval, or don't have thresholds defined,
      # return True as a signal to deploy.
      # TODO: is this the right default?
      return True




if __name__ == '__main__':
	import kfp
	kfp.components.func_to_container_op(automl_eval_metrics,
      output_component_file='tables_eval_metrics_component.yaml', base_image='python:3.7')


# if __name__ == "__main__":
#   automl_eval_threshold('aju-vtests2', 'us-central1',
#       # model_display_name='amy_test3_20191219032001',
#       gcs_path='automl_evals/testing/somodel_1579284627', bucket_name='aju-pipelines')
