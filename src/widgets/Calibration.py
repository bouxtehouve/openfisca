# -*- coding:utf-8 -*-
# Copyright © 2012 Clément Schaff, Mahdi Ben Jelloul

"""
openFisca, Logiciel libre de simulation du système socio-fiscal français
Copyright © 2011 Clément Schaff, Mahdi Ben Jelloul

This file is part of openFisca.

    openFisca is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    openFisca is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with openFisca.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import division

import os

from pandas import read_csv, DataFrame, concat

from PyQt4.QtCore import SIGNAL, Qt, QString, QSize 
from PyQt4.QtGui import (QWidget, QLabel, QDockWidget, QHBoxLayout, QVBoxLayout, 
                         QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, 
                         QInputDialog, QFileDialog, QMessageBox, QApplication, 
                         QIcon, QPixmap, QCursor, QSpacerItem, QSizePolicy)
from core.qthelpers import MyComboBox, MySpinBox, MyDoubleSpinBox, DataFrameViewWidget

try:
    _fromUtf8 = QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

from widgets.matplotlibwidget import MatplotlibWidget

from Config import CONF
from core.columns import BoolCol, AgesCol, EnumCol


class CalibrationWidget(QDockWidget):
    def __init__(self, parent = None):
        super(CalibrationWidget, self).__init__(parent)

        # Create geometry
        self.setWindowTitle("Calibration")
        self.setObjectName("Calibration")
        self.dockWidgetContents = QWidget()        

        self.param = {}
        self.inputs = None
        self.outputs = None
        self.frame = None
        
        self.input_margins_df = None
        self.output_margins_df   = None

        # Parameters widgets

        up_spinbox = MyDoubleSpinBox(self.dockWidgetContents, 'Ratio maximal','','',min_=1, max_=100, step=1, value = CONF.get('calibration', 'up'), changed = self.set_param)
        invlo_spinbox = MyDoubleSpinBox(self.dockWidgetContents, 'Inverse du ratio minimal','','',min_=1, max_=100, step=1, value = CONF.get('calibration', 'invlo'), changed = self.set_param)                 
        method_choices = [(u'Linéaire', 'linear'),(u'Raking ratio', 'raking ratio'), (u'Logit', 'logit')]
        method_combo = MyComboBox(self.dockWidgetContents, u'Choix de la méthode', method_choices)
        self.connect(method_combo.box, SIGNAL('currentIndexChanged(int)'), self.set_param)        
        self.param_widgets = {'up': up_spinbox.spin, 'invlo': invlo_spinbox.spin, 'method': method_combo.box}        

        self.aggregate_calculated = False

        # Total population widget
        self.totalpop = None
        self.ini_totalpop = 0
        
        
        self.ini_totalpop_label = QLabel("", parent = self.dockWidgetContents) 
        self.pop_checkbox = QCheckBox(u"Ajuster", self.dockWidgetContents)
        self.pop_spinbox = MySpinBox(self.dockWidgetContents, u" Cible :", "", option = None ,min_=15e6, max_=30e6, step=5e6, changed = self.set_totalpop)
        self.pop_spinbox.setDisabled(True)
        
        # Margins table view
        self.view = DataFrameViewWidget(self.dockWidgetContents)
        
        # Add/Remove margin button 
                
        self.add_rmv_var_btn  = QPushButton(u'Ajouter/Retirer une variable', self.dockWidgetContents)
        
        self.save_btn = QPushButton(self)
        self.save_btn.setToolTip(QApplication.translate("Calage", "Sauvegarder les paramètres et cales actuels", None, QApplication.UnicodeUTF8))
        self.save_btn.setText(_fromUtf8(""))
        icon = QIcon()
        icon.addPixmap(QPixmap(_fromUtf8(":/images/document-save.png")), QIcon.Normal, QIcon.Off)
        self.save_btn.setIcon(icon)
        self.save_btn.setIconSize(QSize(22, 22))
        
        self.open_btn = QPushButton(self.dockWidgetContents)
        self.open_btn.setToolTip(QApplication.translate("Parametres", "Ouvrir des paramètres", None, QApplication.UnicodeUTF8))
        self.open_btn.setText(_fromUtf8(""))
        icon1 = QIcon()
        icon1.addPixmap(QPixmap(_fromUtf8(":/images/document-open.png")), QIcon.Normal, QIcon.Off)
        self.open_btn.setIcon(icon1)
        self.open_btn.setIconSize(QSize(22, 22))
        self.open_btn.setObjectName(_fromUtf8("open_btn"))

        # Build layouts
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        verticalLayout = QVBoxLayout(self.dockWidgetContents)
        calib_lyt = QHBoxLayout()
        calib_lyt.addWidget(self.save_btn)
        calib_lyt.addWidget(self.open_btn)
        calib_lyt.addItem(spacerItem)
        calib_lyt.addWidget(up_spinbox)
        calib_lyt.addWidget(invlo_spinbox)
        calib_lyt.addWidget(method_combo)
        verticalLayout.addLayout(calib_lyt)

        totalpop_lyt = QHBoxLayout()
        totalpop_lyt.addWidget(self.add_rmv_var_btn)
        totalpop_lyt.addItem(spacerItem)
        totalpop_lyt.addWidget(self.ini_totalpop_label)
        totalpop_lyt.addWidget(self.pop_checkbox)
        totalpop_lyt.addWidget(self.pop_spinbox)
        verticalLayout.addLayout(totalpop_lyt)
        self.init_totalpop()
        verticalLayout.addWidget(self.view)

        # weights ratio plot        
        self.mplwidget = MatplotlibWidget(self.dockWidgetContents)
        verticalLayout.addWidget(self.mplwidget)
        self.setWidget(self.dockWidgetContents)            

        # Connect signals
        self.connect(self.pop_checkbox, SIGNAL('clicked()'), self.set_totalpop)
        self.connect(self.add_rmv_var_btn, SIGNAL('clicked()'), self.add_rmv_var)
        self.connect(self.save_btn, SIGNAL('clicked()'), self.save_config)
        self.connect(self.open_btn, SIGNAL('clicked()'), self.load_config)


        self.connect(self.parent(), SIGNAL('aggregate_calculated()'), self.update_aggregates)
    
    
    def get_add_rmv_var_choices(self):
        '''
        List the available choices for the  add and remove dialog depending on lists contents
        '''
        choices = []
        if self.input_vars_list:
            choices.append((_fromUtf8(u"Ajouter une variable (marge renseignée)"), 'add_input_margin'))
        if self.free_vars_list:
            choices.append((_fromUtf8(u"Ajouter une variable (marge libre)"), 'add_free_margin'))
        if self.output_vars_list:
            choices.append((_fromUtf8(u"Ajouter une variable calculée (marge renseignée)"), 'add_output_margin')),
        if self.table_vars_list:
            choices.append((_fromUtf8(u"Retirer une variable"), 'rmv_margin'))
            choices.append((_fromUtf8(u"Retirer toute les variables"), 'rmv_all_margin'))
        return dict(choices)

    
    def add_rmv_var(self):
        '''
        add or remove variables depending on the content of the add/rmv combobox
        '''
        
        choices = self.get_add_rmv_var_choices()        
        varlabel, ok = QInputDialog.getItem(self.parent(), "Ajouter/Retirer une variable", "Type d'action", 
                                           sorted(choices.keys()))
        result = choices[varlabel]
        insertion = ok and not(varlabel.isEmpty()) #and (varname not in self.margins._vars)
        if insertion:
            if   result == "add_input_margin" : self.add_input_margin()
            elif result == "add_output_margin": self.add_output_margin()
            elif result == "add_free_margin"  : self.add_margin()    
            elif result == "rmv_margin"       : self.rmv_margin()
            elif result == "rmv_all_margin"   : self.reset()    
        return True
    
    @property
    def table_vars_list(self):
        '''
        List of the variables appearing in the table (and the dataframe)
        '''
        if self.frame:
            df = self.frame
            if 'var' in df.columns: 
                return list(df['var'].unique())
        else:
            return []
    
    @property
    def input_vars_list(self):
        if self.input_margins_df is not None:
            df = self.input_margins_df.reset_index()
            #  TODO 'config' 
            set_ic = set(df['var'].unique())
            lic = set_ic.intersection( set(self.inputs.description.col_names))
            return sorted(list(lic - set(self.table_vars_list)))
        else:
            return []
    
    @property
    def free_vars_list(self):
        if self.inputs:
            return sorted(list(set(self.inputs.col_names) - set(self.table_vars_list)))
        else:
            return []
    
    @property
    def output_vars_list(self):
        if self.output_margins_df is not None:
            df = self.output_margins_df.reset_index() 
            #   data_oc = df[ df['source'] == 'output'] # + df['source'] == 'config']
            set_oc = set(df['var'].unique())
            loc = set_oc.intersection( set(self.outputs.description.col_names))
            return sorted(list(loc - set(self.table_vars_list)))
        else:
            return []
    
    def set_totalpop(self):
        if self.pop_checkbox.isChecked():
            self.pop_spinbox.setEnabled(True)
            self.pop_spinbox.spin.setEnabled(True)
            if self.pop_spinbox.spin.isEnabled():
                self.totalpop = self.pop_spinbox.spin.value()
        else:
            self.pop_spinbox.setDisabled(True)
            self.pop_spinbox.spin.setDisabled(True)
            self.totalpop = None    
        self.param_or_margins_changed()

    def init_totalpop(self):
        if self.totalpop:
            self.pop_checkbox.setChecked(True)
            self.pop_spinbox.setEnabled(True)
            self.pop_spinbox.spin.setEnabled(True)
            self.pop_spinbox.spin.setValue(self.totalpop)
        else:
            self.pop_checkbox.setChecked(False)
            self.pop_spinbox.setDisabled(True)
            self.pop_spinbox.spin.setDisabled(True)
        
    def update_aggregates(self):
        self.set_output_margins_from_file()
        self.aggregate_calculated = True

    def param_or_margins_changed(self):
        self.update_view()
        self.emit(SIGNAL('param_or_margins_changed()'))
        
    def update_view(self):
        self.view.clear()
        if self.frame is not None:
            df = self.frame.reset_index()
            df_view = df[ ["var", u"modalités", "cible", u"cible ajustée", "marge", "marge initiale", "variable" ]]            
            self.view.set_dataframe(df_view)
#            (self.view).set_role('Edit', ["cible"])
        self.view.reset()    
                
    def set_inputs_margins_from_file(self, filename = None, year = None):
        if year is None:
            year     = str(CONF.get('simulation','datesim').year)
        if filename is None:
            fname    = CONF.get('calibration','inputs_filename')
            data_dir = CONF.get('paths', 'data_dir')
            filename = os.path.join(data_dir, fname)
        self.set_margins_from_file(filename, year, source="input")
        self.init_totalpop()
        
    def set_output_margins_from_file(self, filename = None, year = None):
        if year is None:
            year     = str(CONF.get('simulation','datesim').year)
        if filename is None:
            fname    = CONF.get('calibration','pfam_filename')
            data_dir = CONF.get('paths', 'data_dir')
            filename = os.path.join(data_dir, fname)
        self.set_margins_from_file(filename, year, source='output')    
        
    def add_margin(self,  source='free'):
        '''
        Add a margin
        '''
        datatables = {'input': self.inputs, 'output': self.outputs, 'free': self.inputs}
        lists      = {'input': self.input_vars_list, 'output': self.output_vars_list, 'free': self.free_vars_list}
        variables_list = lists[source]
        datatable = datatables[source]   
        varnames = {} # {varname: varlabel}
        for var in variables_list:
            varcol  = datatable.description.get_col(var)
            if varcol.label:
                varnames[_fromUtf8(varcol.label)] = var
            else:
                varnames[_fromUtf8(var)] = var        
        varlabel, ok = QInputDialog.getItem(self.parent(), "Ajouter une variable", "Nom de la variable", 
                                           sorted(varnames.keys()))
        varname = varnames[varlabel]
        insertion = ok and not(varlabel.isEmpty()) #and (varname not in self.margins._vars)
        if insertion:
            target = None
            if source=='input' and self.input_margins_df is not None:
                index = self.input_margins_df.index
                indices = [ (var, mod)  for (var, mod) in index if var==varname ]
                target_df = (self.input_margins_df['target'][indices]).reset_index()
                target = dict(zip(target_df['mod'] ,target_df['target']))
            
            self.add_var(varname, target = target, source=source)
            self.param_or_margins_changed()

            
    def add_var(self, varname, target=None, source = 'free'):
        '''
        Add a variable in the dataframe
        '''    
        inputs = self.inputs
        outputs = self.outputs        
        w_init = inputs.get_value("wprm_init", inputs.index['men'])
        w = inputs.get_value("wprm", inputs.index['men'])
        try:
            varcol = inputs.description.get_col(varname)
            value = inputs.get_value(varname, inputs.index['men'])
        except:
            try: 
                varcol = outputs.description.get_col(varname)
                value = outputs.get_value(varname, inputs.index['men'])
            except:                
                print "Variable %s is absent from both inputs and outputs" %varname
                return            
        label = varcol.label
        # TODO: rewrite this using pivot table
        items = [ ('marge'    , w  ),
                ('marge initiale' , w_init ),
                ('mod',   value)]
        df = DataFrame.from_items(items)
        res = df.groupby('mod', sort= True).sum()
        res.insert(0, u"modalités",u"")
        res.insert(2, "cible", 0)
        res.insert(2, u"cible ajustée", 0)
        res.insert(4, "source", source)
        mods = res.index

        if target is not None:
            if len(mods) != len(target.keys()):
                print 'Problem with variable : ', varname
                print len(target.keys()), ' target keys for ', len(mods), ' modalities' 
                print 'Skipping the variable'
                drop_indices = [ (varname, mod) for mod in target.keys()]
                if source == 'input':                    
                    self.input_margins_df = self.input_margins_df.drop(drop_indices)
                    self.input_margins_df.index.names = ['var','mod']
                if source == 'output':
                    self.output_margins_df = self.output_margins_df.drop(drop_indices)
                    self.output_margins_df.index.names = ['var','mod']
                return

        if isinstance(varcol, EnumCol):
            if varcol.enum:
                enum = varcol.enum
                res[u'modalités'] = [enum._vars[mod] for mod in mods]
            else:
                res[u'modalités'] = [mod for mod in mods]
        elif isinstance(varcol, BoolCol):
            res[u'modalités'] = bool(mods)
        elif isinstance(varcol, AgesCol):
            res[u'modalités'] = mods
        else:
            res[u'modalités'] = "total"

        res['var'] = varname
        if label is not None:
            res['variable'] = label
        else:
            res['variable'] = varname

        if target is not None:
            for mod, margin in target.iteritems():
                res['cible'][mod] = margin     

        res = concat([DataFrame(), res], verify_integrity = True, keys = ['', varname])
                        
        if self.frame is None:
            self.frame = res
        else: 
            self.frame = concat([self.frame, res], verify_integrity = True)
 
 
    def add_output_margin(self):
        QMessageBox.critical(
                    self, "Erreur", u"Pas encore implémenté",
                    QMessageBox.Ok, QMessageBox.NoButton)
        # TODO: uncomment this wehn implemented self.add_margin(from_output=True)
        self.emit(SIGNAL('calibrated()'))
    
    def add_input_margin(self):
        self.add_margin(source='input')
        
    def rmv_margin(self, all_vars = False):
        '''
        Remove margins (all by default)
        '''
        if all_vars:
            self.frame = DataFrame()
            self.param_or_margins_changed()
            return
        varnames = {}
        vars_in_table = self.frame['var'].unique() 
        for var in vars_in_table:
            if var in  self.output_vars_list:
                datatable = self.outputs
            else:
                datatable = self.inputs
            varcol  = datatable.description.get_col(var)
            if varcol.label:
                varnames[_fromUtf8(varcol.label)] = var
            else:
                varnames[_fromUtf8(var)] = var       
        if not all_vars:
            varlabel, ok = QInputDialog.getItem(self.parent(), "Retirer une variable", u"Nom de la variable à retirer", 
                                           sorted(varnames.keys()))
            varname = varnames[varlabel]
            deletion = ok and not(varlabel.isEmpty())
            if deletion:
                df = self.frame 
                cleaned = df[df['var'] != varname]
                self.frame = cleaned
        self.param_or_margins_changed()
                                
    def init_param(self):
        '''
        Set initial values of parameters from configuration settings 
        '''
        for parameter in self.param_widgets:
            widget = self.param_widgets[parameter]
            if isinstance(widget, QComboBox):
                for index in range(widget.count()):
                    if unicode(widget.itemData(index).toString()
                               ) == unicode(CONF.get('calibration', 'method')):
                        break
                widget.setCurrentIndex(index)
                
    def set_param(self):
        '''
        Set parameters from box widget values
        '''
        for parameter, widget in self.param_widgets.iteritems():
            if isinstance(widget, QComboBox):
                data = widget.itemData(widget.currentIndex())                
                self.param[parameter] = unicode(data.toString())
            if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                self.param[parameter] = widget.value()
        self.param_or_margins_changed()        
        return True

    def set_inputs(self, inputs):
        inputs.gen_index(['men', 'fam', 'foy']) # TODO: REMOVE ? test this
        self.inputs = inputs
        self.ini_totalpop = sum(inputs.get_value("wprm_init", inputs.index['men']))
        label_str = u"Population initiale totale :" + str(int(round(self.ini_totalpop))) + u" ménages"
        self.ini_totalpop_label.setText(label_str)

        
    def reset(self):
        self.frame = None
        inputs = self.inputs
        inputs.set_value('wprm', inputs.get_value('wprm_init'),inputs.index['ind'])
        self.pop_checkbox.setChecked(False)        
        self.pop_spinbox.setDisabled(True)
        self.pop_spinbox.spin.setDisabled(True)
        self.set_totalpop()
        self.plotWeightsRatios()
                
#    def update_output_margins(self):
#        datatable = self.outputs
#        inputs    = self.inputs
#        w = inputs.get_value("wprm", inputs.index['men']) # TODO wprm_init ?
#        for varname in datatable.description.col_names:
#            varcol = datatable.description.get_col(varname)
#            value = datatable.get_value(varname, inputs.index['men'])            
#            
#            if isinstance(varcol , BoolPresta):
#                self.margins._output_vars[varname] = {}
#                self.margins._output_vars[varname][True]  = sum(w*(value == True))
#                self.margins._output_vars[varname][False] = sum(w*(value == False))
#            else:
#                self.margins._output_vars[varname] = sum(w*(value))
    
    def get_param(self):
        p = {}
        p['method'] = self.param['method']
        p['lo']     = 1/self.param['invlo']
        p['up']     = self.param['up']
        p['use_proportions'] = True
        p['pondini']  = 'wprm_init'
        return p
              
    def calibrate(self):
        '''
        Calibrate accoding to margins found in frame
        '''
        df = self.frame
        inputs = self.inputs
        outputs = self.outputs
        margins = {}
        for var, mod in df.index:
            if not margins.has_key(var):
                margins[var] = {}
            margins[var][mod] =  df.get_value((var,mod), 'cible')
        param = self.get_param()
        if self.totalpop is not None:
            margins['totalpop'] = self.totalpop
        try:
            adjusted_margins = inputs.update_weights(margins, param=param, return_margins = True)
        except Exception, e:
            raise Exception(u"Vérifier les paramètres:\n%s"% e)
        
        w = inputs.get_value("wprm", inputs.index['men'])
        for varname in set([var for var, mod in df.index]): 
            try:
                value = inputs.get_value(varname, inputs.index['men'])
            except:
                try: 
                    value = outputs.get_value(varname, inputs.index['men'])
                except:                
                    print "Calibration : Variable %s is absent from both inputs and outputs" %varname
            items = [('marge', w  ),('mod', value)]
            updated_margins = DataFrame.from_items(items).groupby('mod', sort= True).sum()
            for mod in set([mod for var, mod in df.index if var == varname]):
                df.set_value((varname,mod), u"cible ajustée", adjusted_margins[varname][mod])
                df.set_value((varname,mod), u"marge", updated_margins['marge'][mod])
        self.update_view()
        self.plotWeightsRatios()
        self.emit(SIGNAL('calibrated()'))
                    
    def plotWeightsRatios(self):
        ax = self.mplwidget.axes
        ax.clear()
        weight_ratio = self.inputs.get_value('wprm')/self.inputs.get_value('wprm_init')
        ax.hist(weight_ratio, 50, normed=1, histtype='stepfilled')
        ax.set_xlabel(u"Poids relatifs")
        ax.set_ylabel(u"Densité")
        self.mplwidget.draw()
        
    def save_config(self):
        '''
        Save calibration parameters
        '''
        # TODO: add  param
        # param_dict = self.get_param()
        year     = str(CONF.get('simulation','datesim').year)
        df = self.frame
        if len(df['var']) == 0:
            QMessageBox.critical(
                    self, "Erreur", u"Les marges sont vides" ,
                    QMessageBox.Ok, QMessageBox.NoButton)
            return
        
        saved = DataFrame(index = df.index, columns = [year], data=df['cible']).reset_index()
        saved = saved.append({'level_0' : 'totalpop',
                      'level_1' : 0,
                      year      : self.totalpop}, 
                      ignore_index = True)
        
        
        saved = saved.rename(columns = { 'level_0' : 'var', 'level_1'  : 'mod'} )
        calib_dir = CONF.get('paths','calib_dir')
        default_fileName = os.path.join(calib_dir, 'sans-titre')
        fileName = QFileDialog.getSaveFileName(self,
                                               u"Enregistrer un calage", default_fileName, u"Calage OpenFisca (*.csv)")
        if fileName:
            try:
                saved.to_csv(fileName, index=False)
            except Exception, e:
                QMessageBox.critical(
                    self, "Erreur", u"Impossible d'enregistrer le fichier : " + str(e),
                    QMessageBox.Ok, QMessageBox.NoButton)
        
    def load_config(self):
        year     = str(CONF.get('simulation','datesim').year)
        calib_dir = CONF.get('paths','calib_dir')
        fileName = QFileDialog.getOpenFileName(self,
                                               u"Ouvrir un calage", calib_dir, u"Calages OpenFisca (*.csv)")
        if not fileName == '':
            try: 
                QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
                self.set_margins_from_file(fileName, year = year, source='config')
                self.init_totalpop()
            except Exception, e:
                QMessageBox.critical(
                    self, "Erreur", u"Impossible de lire le fichier : " + str(e),
                    QMessageBox.Ok, QMessageBox.NoButton)
            finally:
                QApplication.restoreOverrideCursor()    
            self.param_or_margins_changed()

    def set_margins_from_file(self, filename, year, source):
        try:
            f_tot = open(filename)
            totals = read_csv(f_tot,index_col = (0,1))
            marges = {}
            if source == 'input':
                self.input_margins_df = DataFrame({'target':totals[year]})
            elif source =='output':
                self.output_margins_df = DataFrame({'target':totals[year]})
                
            for var, mod in totals.index:
                if not marges.has_key(var):
                    marges[var] = {}
                marges[var][mod] =  totals.get_value((var,mod),year)
                
            for var in marges.keys():
                if var == 'totalpop': 
                    if source == "input" or source == "config" :
                        totalpop = marges.pop('totalpop')[0]
                        marges['totalpop'] = totalpop
                        self.totalpop = totalpop
                else:
                    self.add_var(var, marges[var], source = source)
        except Exception, e:
            print Warning("Unable to read %(source)s margins for %(year)s, margins left empty because %(e)s" % {'source':source, 'year': year, 'e':e})
        finally:
            f_tot.close()