import os
import shutil
import pytest
import pandas as pd
from processor.main import main
import processor.reporting.utils as utl
import processor.reporting.analyze as az
import processor.reporting.vmcolumns as vmc
import processor.reporting.vendormatrix as vm
import processor.reporting.dictcolumns as dctc


@pytest.fixture(scope='module')
def load_config():
    test_path = 'tests'
    tmp_path_str = 'tmp'
    file_name = 'end_to_end_config.xlsx'
    tmp_path = os.path.join(test_path, tmp_path_str)
    utl.dir_check(tmp_path)
    load_config = utl.import_read_csv(os.path.join(test_path, file_name))
    for old_path in [utl.config_path, utl.dict_path, utl.raw_path]:
        full_new_path = os.path.join(tmp_path, old_path)
        utl.dir_check(full_new_path)
        utl.dir_check(old_path)
        utl.copy_tree_no_overwrite(old_path, full_new_path, log=False,
                                   overwrite=True)
        if old_path != utl.config_path:
            shutil.rmtree(old_path)
        else:
            base_vm = os.path.join(test_path, vm.csv_file)
            if os.path.exists(base_vm):
                vm_file = os.path.join(utl.config_path, vm.csv_file)
                utl.copy_file(base_vm, vm_file)
        if old_path == utl.dict_path:
            new_t = os.path.join(full_new_path, dctc.filepath_tran_config)
            old_t = os.path.join(old_path, dctc.filepath_tran_config)
            utl.dir_check(old_t)
            utl.copy_tree_no_overwrite(new_t, old_t, log=False, overwrite=True)
            base_td = os.path.join(test_path, dctc.filename_tran_config)
            if os.path.exists(base_td):
                td_file = os.path.join(old_t, dctc.filename_tran_config)
                utl.copy_file(base_td, td_file)
        if old_path == utl.raw_path:
            utl.dir_check(utl.raw_path)
            test_raw_file = os.path.join(test_path, 'rawfile.csv')
            utl.copy_file(test_raw_file, utl.raw_path)
    if os.path.exists(az.Analyze.analysis_dict_file_name):
        os.remove(az.Analyze.analysis_dict_file_name)
    yield load_config
    for old_path in [utl.config_path, utl.dict_path, utl.raw_path]:
        utl.dir_check(old_path)
        full_new_path = os.path.join(tmp_path, old_path)
        utl.copy_tree_no_overwrite(full_new_path, old_path, log=False,
                                   overwrite=True)
        shutil.rmtree(full_new_path)


@pytest.mark.usefixtures('load_config')
class TestEndToEnd:
    """
    If test suite appears to run infinitely, check that the following files
    are in the 'processor/tests/' directory and up to date:
    * 'end_to_end_config.xlsx'
    * 'rawfile.csv'
    * 'results.csv'
    Also, check that the file 'end_to_end_config.csv' is in the
    'processor/config/' directory and up to date
    """
    def test_load_config(self, load_config):
        config_cols = [vm.ImportConfig.key, vm.ImportConfig.account_id,
                       vm.ImportConfig.filter, vm.ImportConfig.name,
                       vmc.startdate, vmc.enddate, vmc.apifields]
        assert config_cols == load_config.columns.to_list()

    def test_config_to_vm(self, load_config):
        for col in [vmc.vendorkey, vmc.apifields]:
            load_config[col] = ''
        cols = [vmc.startdate, vmc.enddate]
        load_config = utl.data_to_type(load_config, str_col=cols)
        load_config = load_config.to_dict(orient='records')
        ic = vm.ImportConfig()
        ic.add_and_remove_from_vm(load_config, matrix=True)
        matrix = vm.VendorMatrix()
        for x in load_config:
            vk_parts = (x[vm.ImportConfig.key], x[vm.ImportConfig.name])
            vk = 'API_{}_{}'.format(*vk_parts)
            assert vk in matrix.vm_df[vmc.vendorkey].values
            matrix.vm_change_on_key(vk, vmc.enddate, x[vmc.enddate])
            if x[vmc.apifields]:
                matrix.vm_change_on_key(vk, vmc.apifields, x[vmc.apifields])
        matrix.write()

    def test_run_processor(self):
        """
        If this test appears to be running infinitely, note this test takes a
        much longer time than the others due to its large scope. If it
        concerns you, run it on debug and monitor the console output as it runs
        to ensure the test is progressing as expected.
        """
        main('--api all --analyze')

    def test_check_results(self):
        group_cols = [vmc.vendorkey, vmc.date, dctc.CAM, dctc.VEN, dctc.COU,
                      dctc.ENV]
        metric_cols = [vmc.impressions, vmc.clicks, vmc.cost]
        df = utl.import_read_csv(vmc.output_file)
        df = df.groupby(group_cols)[metric_cols].sum().reset_index()
        file_name = os.path.join('tests', 'results.csv')
        rdf = utl.import_read_csv(file_name)
        rdf = rdf.groupby(group_cols)[metric_cols].sum().reset_index()
        vk_df_mismatch = []
        for vendor_key in rdf[vmc.vendorkey].unique():
            df_vk = df[df[vmc.vendorkey] == vendor_key].sort_values(
                group_cols).reset_index(drop=True)
            rdf_vk = rdf[rdf[vmc.vendorkey] == vendor_key].sort_values(
                group_cols).reset_index(drop=True)
            try:
                pd.testing.assert_frame_equal(df_vk, rdf_vk)
            except AssertionError as e:
                vk_df_mismatch.append(f"vendorkey={vendor_key}:\n{str(e)}")
        if vk_df_mismatch:
            full_msg = "\n\n".join(vk_df_mismatch)
            full_msg = (f"Mismatch found for the following "
                        f"vendorkeys:\n\n{full_msg}")
            pytest.fail(full_msg)
