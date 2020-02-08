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


import kfp.dsl as dsl
import kfp.gcp as gcp
import kfp.components as comp
from kfp.dsl.types import GCSPath, String
import json
# import time

DEFAULT_SCHEMA = json.dumps({"end_station_id": "CATEGORY", "start_station_id": "CATEGORY", "loc_cross": "CATEGORY", "bike_id": "CATEGORY"})

create_dataset_op = comp.load_component_from_file(
  './create_dataset_for_tables/tables_component.yaml'
  )
import_data_op = comp.load_component_from_file(
  './import_data_from_bigquery/tables_component.yaml'
  )
set_schema_op = comp.load_component_from_file(
  './import_data_from_bigquery/tables_schema_component.yaml'
  )
train_model_op = comp.load_component_from_file(
    './create_model_for_tables/tables_component.yaml')
eval_model_op = comp.load_component_from_file(
    './create_model_for_tables/tables_eval_component.yaml')
eval_metrics_op = comp.load_component_from_file(
    './create_model_for_tables/tables_eval_metrics_component.yaml')
deploy_model_op = comp.load_component_from_file(
    './deploy_model_for_tables/tables_deploy_component.yaml'
    )

@dsl.pipeline(
  name='AutoML Tables',
  description='Demonstrate an AutoML Tables workflow'
)
def automl_tables_test(  #pylint: disable=unused-argument
  gcp_project_id: String = 'YOUR_PROJECT_HERE',
  gcp_region: String = 'us-central1',
  dataset_display_name: String = 'YOUR_DATASET_NAME',
  api_endpoint: String = '',
  path: String = 'bq://aju-dev-demos.london_bikes_weather.bikes_weather',
  target_col_name: String = 'duration',
  time_col_name: String = '',
  # test_train_col_name: String = '',
 # schema dict with col name as key, type as value
  schema_info: String = DEFAULT_SCHEMA,
  train_budget_milli_node_hours: 'Integer' = 1000,
  model_prefix: String = 'bwmodel',
  model_display_name: String = 'bwmodel_1579017140',
  bucket_name: String = 'aju-pipelines',
  thresholds: str = '{"au_prc": 0.9}',

  ):

  eval_model = eval_model_op(
    gcp_project_id=gcp_project_id,
    gcp_region=gcp_region,
    bucket_name=bucket_name,
    # gcs_path='automl_evals/{}/evalstring'.format(dsl.RUN_ID_PLACEHOLDER),
    api_endpoint=api_endpoint,
    model_display_name=model_display_name
    )  #.apply(gcp.use_gcp_secret('user-gcp-sa'))

  eval_metrics = eval_metrics_op(
    gcp_project_id=gcp_project_id,
    gcp_region=gcp_region,
    bucket_name=bucket_name,
    api_endpoint=api_endpoint,
    model_display_name=model_display_name,
    thresholds=thresholds,
    eval_data=eval_model.outputs['eval_data'],
    # gcs_path=eval_model.outputs['evals_gcs_path']
    )  #.apply(gcp.use_gcp_secret('user-gcp-sa'))

  with dsl.Condition(eval_metrics.outputs['deploy'] == True):
    deploy_model = deploy_model_op(
      gcp_project_id=gcp_project_id,
      gcp_region=gcp_region,
      api_endpoint=api_endpoint,
      model_display_name=model_display_name
      )  #.apply(gcp.use_gcp_secret('user-gcp-sa'))


if __name__ == '__main__':
  import kfp.compiler as compiler
  compiler.Compiler().compile(automl_tables_test, __file__ + '.tar.gz')
