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
from kfp.dsl.types import GCSPath, String, Dict


create_dataset_op = comp.load_component_from_file(
  './tables_component.yaml'  # pylint: disable=line-too-long
  )

import_data_op = comp.load_component_from_file(
  '../import_data_from_bigquery/tables_component.yaml' # pylint: disable=line-too-long
  )

set_schema_op = comp.load_component_from_file(
  '../import_data_from_bigquery/tables_schema_component.yaml' # pylint: disable=line-too-long
  )

@dsl.pipeline(
  name='AutoML Tables',
  description='Demonstrate an AutoML Tables workflow'
)
def automl_tables(  #pylint: disable=unused-argument
  gcp_project_id: String = 'YOUR_PROJECT_HERE',
  gcp_region: String = 'us-central1',
  display_name: String = 'YOUR_DATASET_NAME',
  api_endpoint: String = '',
  tables_dataset_metadata: Dict = {},
  path: String = 'bq://aju-dev-demos.london_bikes_weather.bikes_weather',
  target_col_name: String = 'duration',
  time_col_name: String = '',
  test_train_col_name: String = '',
 # schema dict with col name as key, type as value
  schema_info: Dict = {"end_station_id": "CATEGORY", "start_station_id": "CATEGORY", "loc_cross": "CATEGORY", "bike_id": "CATEGORY"},
  ):


  create_dataset = create_dataset_op(
    gcp_project_id=gcp_project_id,
    gcp_region=gcp_region,
    display_name=display_name,
    api_endpoint=api_endpoint,
    tables_dataset_metadata=tables_dataset_metadata
    ).apply(gcp.use_gcp_secret('user-gcp-sa'))


  import_data = import_data_op(
    gcp_project_id=gcp_project_id,
    gcp_region=gcp_region,
    display_name=display_name,
    api_endpoint=api_endpoint,
    path=path
    ).apply(gcp.use_gcp_secret('user-gcp-sa'))

  set_schema = set_schema_op(
    gcp_project_id=gcp_project_id,
    gcp_region=gcp_region,
    display_name=display_name,
    api_endpoint=api_endpoint,
    target_col_name=target_col_name,
    schema_info=schema_info,
    time_col_name=time_col_name,
    test_train_col_name=test_train_col_name
    ).apply(gcp.use_gcp_secret('user-gcp-sa'))


  import_data.after(create_dataset)
  set_schema.after(import_data)


if __name__ == '__main__':
  import kfp.compiler as compiler
  compiler.Compiler().compile(automl_tables, __file__ + '.tar.gz')
