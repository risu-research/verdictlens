"""VerdictLens V16 - deliberately plain native desktop evidence inspector.

Requires only Python 3 with Tkinter. No browser, server, packages, or network
needed for inspection. External links open only when explicitly requested.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))
from github_import import load_github_bundle
from verdictlens_core import (load_audit, verify_structure, role_name, state_name,
    safe_github_url, witness, write_json, SCOPE)

class Inspector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('VerdictLens V16 - Check Run Inspector')
        self.geometry('1170x790')
        self.minsize(920,660)
        try:
            # Native platform theme, not themed dashboard CSS.
            available=ttk.Style(self).theme_names()
            if sys.platform=='win32' and 'vista' in available:
                ttk.Style(self).theme_use('vista')
        except Exception:
            pass
        self.original=load_audit(ROOT/'data/v9_audit.json',bundled=True)
        self.data=self.original
        self.imported=False
        self.case_index=0
        self.check_index=0
        self.subject_index=0
        self.notes={}
        self.case_var=tk.StringVar()
        self.filter_var=tk.StringVar()
        self.view_var=tk.StringVar(value='All recorded checks')
        self.summary_var=tk.StringVar()
        self.check_var=tk.StringVar()
        self.role_var=tk.StringVar()
        self.status_var=tk.StringVar()
        self.detail_vars={x:tk.StringVar() for x in ('Status','SHA','Check Run ID','GitHub App ID','Conclusion','Finding')}
        self.render_layout()
        self.select_case(0)

    def render_layout(self):
        menubar=tk.Menu(self)
        file_menu=tk.Menu(menubar,tearoff=False)
        file_menu.add_command(label='Open audit JSON...',command=self.import_audit)
        file_menu.add_command(label='Open GitHub Check Runs JSON...',command=self.import_github)
        file_menu.add_command(label='Save full audit JSON...',command=self.export_audit)
        file_menu.add_command(label='Save selected witness...',command=self.export_witness)
        file_menu.add_separator()
        file_menu.add_command(label='Restore bundled evidence',command=self.restore)
        file_menu.add_separator()
        file_menu.add_command(label='Exit',command=self.destroy)
        menubar.add_cascade(label='File',menu=file_menu)
        evidence=tk.Menu(menubar,tearoff=False)
        evidence.add_command(label='Open pull request on GitHub',command=self.open_pr)
        evidence.add_command(label='Open selected Check Run on GitHub',command=self.open_run)
        evidence.add_command(label='Copy commit SHA',command=lambda:self.copy_field('SHA'))
        evidence.add_command(label='Copy Check Run ID',command=lambda:self.copy_field('Check Run ID'))
        evidence.add_command(label='Show selected check evidence JSON',command=self.show_raw)
        menubar.add_cascade(label='Evidence',menu=evidence)
        tools=tk.Menu(menubar,tearoff=False)
        tools.add_command(label='Notes...',command=self.open_notes)
        tools.add_command(label='Evidence scope / policy...',command=self.open_policy)
        menubar.add_cascade(label='Tools',menu=tools)
        help_menu=tk.Menu(menubar,tearoff=False)
        help_menu.add_command(label='About...',command=self.about)
        menubar.add_cascade(label='Help',menu=help_menu)
        self.config(menu=menubar)

        base=ttk.Frame(self,padding=(10,8,10,7))
        base.pack(fill='both',expand=True)
        header=ttk.Frame(base)
        header.pack(fill='x',pady=(0,8))
        ttk.Label(header,text='VerdictLens',font=('Segoe UI',11,'bold')).pack(side='left')
        ttk.Label(header,text='    Check Run Inspector  /  v16  /  offline evidence',font=('Segoe UI',9)).pack(side='left')

        controls=ttk.LabelFrame(base,text='Selection',padding=(8,6))
        controls.pack(fill='x',pady=(0,8))
        ttk.Label(controls,text='Pull request').grid(row=0,column=0,sticky='w',padx=(0,5))
        self.case_combo=ttk.Combobox(controls,textvariable=self.case_var,state='readonly',width=42)
        self.case_combo.grid(row=0,column=1,sticky='ew',padx=(0,12))
        self.case_combo.bind('<<ComboboxSelected>>',lambda e:self.select_case(self.case_combo.current()))
        ttk.Label(controls,text='Show').grid(row=0,column=2,sticky='w',padx=(0,5))
        self.view_combo=ttk.Combobox(controls,textvariable=self.view_var,state='readonly',width=19,
            values=['All recorded checks','Contrasts only','Incomplete only'])
        self.view_combo.grid(row=0,column=3,sticky='ew',padx=(0,12))
        self.view_combo.bind('<<ComboboxSelected>>',lambda e:self.fill_checks())
        ttk.Label(controls,text='Find').grid(row=0,column=4,sticky='w',padx=(0,5))
        find=ttk.Entry(controls,textvariable=self.filter_var,width=24)
        find.grid(row=0,column=5,sticky='ew')
        self.filter_var.trace_add('write',lambda *_:self.fill_checks())
        controls.grid_columnconfigure(1,weight=3)
        controls.grid_columnconfigure(5,weight=2)

        matrix=ttk.LabelFrame(base,text='Recorded check outcomes',padding=(7,6))
        matrix.pack(fill='both',expand=True,pady=(0,8))
        self.matrix=ttk.Treeview(matrix,columns=('check','a','b','c','finding'),show='headings',selectmode='browse',height=10)
        self.matrix.heading('check',text='Check context');self.matrix.column('check',width=525,minwidth=180,anchor='w',stretch=True)
        for col in ('a','b','c'):
            self.matrix.heading(col,text='');self.matrix.column(col,width=100,minwidth=80,anchor='w',stretch=False)
        self.matrix.heading('finding',text='Finding')
        self.matrix.column('finding',width=190,minwidth=150,stretch=False)
        scroll=ttk.Scrollbar(matrix,orient='vertical',command=self.matrix.yview)
        self.matrix.configure(yscrollcommand=scroll.set)
        self.matrix.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        self.matrix.bind('<<TreeviewSelect>>',self.on_check_change)
        self.matrix.bind('<Double-1>',lambda e:self.focus_subject())
        self.matrix.bind('<Return>',lambda e:self.focus_subject())
        self.summary_label=ttk.Label(base,textvariable=self.summary_var,anchor='w')
        self.summary_label.pack(fill='x',pady=(0,7))

        lower=ttk.LabelFrame(base,text='Selected check / source records',padding=(8,7))
        lower.pack(fill='x')
        ttk.Label(lower,text='Check').grid(row=0,column=0,sticky='w',padx=(0,8),pady=(0,5))
        ttk.Label(lower,textvariable=self.check_var,font=('Segoe UI',9,'bold'),wraplength=920).grid(row=0,column=1,columnspan=4,sticky='w',pady=(0,5))
        # The core of the demo: actual subject-specific SHA and Check Run, not decoration.
        self.records=ttk.Treeview(lower,columns=('role','state','check_id','sha'),show='headings',height=3,selectmode='browse')
        for col,title,width in [('role','Commit subject',130),('state','Result',115),('check_id','Check Run ID',155),('sha','Commit SHA',485)]:
            self.records.heading(col,text=title);self.records.column(col,width=width,minwidth=75,anchor='w',stretch=(col=='sha'))
        self.records.grid(row=1,column=0,columnspan=5,sticky='ew',pady=(0,6))
        self.records.bind('<<TreeviewSelect>>',self.on_subject_change)
        self.records.bind('<Double-1>',lambda e:self.open_run())
        for label,col,row in [('Status',0,2),('SHA',2,2),('Check Run ID',0,3),('GitHub App ID',2,3),('Conclusion',0,4),('Finding',2,4)]:
            ttk.Label(lower,text=label+':').grid(row=row,column=col,sticky='w',padx=(0,6),pady=2)
            value=ttk.Label(lower,textvariable=self.detail_vars[label],anchor='w',wraplength=340)
            value.grid(row=row,column=col+1,sticky='ew',padx=(0,15),pady=2)
        lower.grid_columnconfigure(1,weight=1)
        lower.grid_columnconfigure(3,weight=1)
        lower.grid_columnconfigure(4,weight=0)
        buttons=ttk.Frame(lower)
        buttons.grid(row=5,column=0,columnspan=5,sticky='w',pady=(7,2))
        for label,cmd in [('Open Check Run',self.open_run),('Copy SHA',lambda:self.copy_field('SHA')),
                          ('Copy Check ID',lambda:self.copy_field('Check Run ID')),
                          ('Export witness...',self.export_witness),('Evidence JSON...',self.show_raw)]:
            ttk.Button(buttons,text=label,command=cmd).pack(side='left',padx=(0,7))
        self.explain=ttk.Label(lower,text='',wraplength=950,justify='left')
        self.explain.grid(row=6,column=0,columnspan=5,sticky='w',pady=(6,1))

        foot=ttk.Frame(base)
        foot.pack(fill='x',pady=(8,0))
        ttk.Separator(foot,orient='horizontal').pack(fill='x',pady=(0,5))
        self.footer=ttk.Label(foot,text='')
        self.footer.pack(side='left')
        ttk.Button(foot,text='Policy / limits...',command=self.open_policy).pack(side='right')
        ttk.Button(foot,text='Save audit...',command=self.export_audit).pack(side='right',padx=(0,6))

    def current_case(self): return self.data['reports'][self.case_index]
    def current_row(self): return self.current_case()['rows'][self.check_index]
    def current_cell(self): return self.current_row()['cells'][self.subject_index]
    def select_case(self,index):
        if index<0 or index>=len(self.data['reports']):return
        self.case_index=index
        self.case_combo['values']=[f"{c['repository']}  |  #{c['pr']}" for c in self.data['reports']]
        self.case_combo.current(index)
        self.filter_var.set('')
        self.view_var.set('All recorded checks')
        self.check_index=next((j for j,r in enumerate(self.current_case()['rows']) if r.get('minimal_witness')),0)
        self.subject_index=0
        self.fill_checks()
        self.update_detail()

    def fill_checks(self):
        if not hasattr(self,'matrix'):return
        c=self.current_case(); roles=c['roles']
        for j,col in enumerate(('a','b','c')):
            if j<len(roles):
                self.matrix.heading(col,text=role_name(roles[j]));self.matrix.column(col,width=109,minwidth=90,stretch=False)
            else:
                self.matrix.heading(col,text='');self.matrix.column(col,width=2,minwidth=2,stretch=False)
        self.matrix.delete(*self.matrix.get_children())
        q=self.filter_var.get().strip().lower()
        for i,r in enumerate(c['rows']):
            if q not in r['context'].lower():continue
            if self.view_var.get()=='Contrasts only' and not r.get('minimal_witness'):continue
            if self.view_var.get()=='Incomplete only' and not any(x['state'] in ('NOT_OBSERVED','PENDING','AMBIGUOUS','INCONCLUSIVE') for x in r['cells']):continue
            states=[state_name(x['state']) for x in r['cells']]
            finding=('CONTRAST' if r.get('minimal_witness') else 'INCOMPLETE' if any(x in states for x in ('NO RECORD','PENDING','AMBIGUOUS','INCONCLUSIVE')) else 'NO CONTRAST')
            self.matrix.insert('','end',iid=str(i),values=(r['context'],*(states+['']*(3-len(states))),finding))
        self.summary_var.set(f"{c['repository']} #{c['pr']}   |   {len(c['rows'])} named checks   |   {c.get('verified_observations','?')} {'supplied Check Runs' if self.imported else 'selected public Check Runs'}")
        if self.matrix.exists(str(self.check_index)):
            self.matrix.selection_set(str(self.check_index));self.matrix.see(str(self.check_index))
        else:
            vals=self.matrix.get_children()
            if vals:self.matrix.selection_set(vals[0])

    def on_check_change(self,event=None):
        selected=self.matrix.selection()
        if not selected:return
        self.check_index=int(selected[0]);r=self.current_row()
        witness_pair=r.get('minimal_witness')
        roles=self.current_case()['roles']
        self.subject_index=roles.index(witness_pair['subjects'][1]) if witness_pair and witness_pair['subjects'][1] in roles else 0
        self.update_detail()

    def update_detail(self):
        r=self.current_row()
        self.check_var.set(r['context'])
        self.records.delete(*self.records.get_children())
        for j,x in enumerate(r['cells']):
            self.records.insert('','end',iid=str(j),values=(role_name(x['role']),state_name(x['state']),x.get('check_id') or '(none)',x['sha']))
        self.records.selection_set(str(self.subject_index))
        self.records.see(str(self.subject_index))
        self.fill_record()

    def on_subject_change(self,event=None):
        selected=self.records.selection()
        if selected:self.subject_index=int(selected[0]);self.fill_record()

    def fill_record(self):
        c=self.current_case();r=self.current_row();x=self.current_cell()
        values={'Status':state_name(x['state']),'SHA':x['sha'],'Check Run ID':str(x.get('check_id') or '(none)'),
                'GitHub App ID':str(x.get('app_id') or r.get('app_id') or '(unknown)'),
                'Conclusion':str(x.get('conclusion') or '(none)'),
                'Finding':'NO CONTRAST' if r['finding']=='SAME_RECORDED_RESULT' else r['finding'].replace('_',' ')}
        for k,v in values.items():self.detail_vars[k].set(v)
        self.explain.config(text=x.get('interpretation') or 'No more recorded interpretation.')
        imported='IMPORTED: source not authenticated' if self.imported else 'Bundled frozen evidence'
        self.footer.config(text=f"{imported}   |   {len(self.data['reports'])} cases   |   Historical enforcement: UNVERIFIED")

    def focus_subject(self):self.records.focus_set()
    def copy_field(self,name):
        x=self.detail_vars[name].get()
        if x and x!='(none)':
            self.clipboard_clear();self.clipboard_append(x);self.update()
    def open_link(self,url):
        safe=safe_github_url(url)
        if safe:webbrowser.open(safe)
        else:messagebox.showinfo('No source','No recorded GitHub URL is available for this item.',parent=self)
    def open_pr(self):self.open_link(self.current_case().get('pr_url'))
    def open_run(self):self.open_link(self.current_cell().get('url'))
    def export_audit(self):
        path=filedialog.asksaveasfilename(parent=self,title='Save evidence audit',defaultextension='.json',initialfile='VerdictLens_Audit.json',filetypes=[('JSON','*.json')])
        if path:
            try:write_json(path,self.data)
            except OSError as e:messagebox.showerror('Save error',str(e),parent=self)
    def export_witness(self):
        c=self.current_case();r=self.current_row()
        if not r.get('minimal_witness'):
            messagebox.showinfo('No contrasting witness','This check has no unambiguous recorded contrasting two-record witness.',parent=self)
            return
        path=filedialog.asksaveasfilename(parent=self,title='Save minimal witness',defaultextension='.json',initialfile=f"VerdictLens_{c['pr']}_Witness.json",filetypes=[('JSON','*.json')])
        if path:
            try:write_json(path,witness(c,r,imported=self.imported))
            except OSError as e:messagebox.showerror('Save error',str(e),parent=self)
    def import_audit(self):
        path=filedialog.askopenfilename(parent=self,title='Open recorded V9 audit',filetypes=[('JSON','*.json'),('All files','*.*')])
        if not path:return
        try:new_data=load_audit(path)
        except Exception as e:messagebox.showerror('Invalid evidence',str(e),parent=self);return
        self.data=new_data;self.imported=True;self.select_case(0)
        messagebox.showinfo('Evidence loaded','Audit format checked. Imported data and URLs have not been independently authenticated.',parent=self)
    def import_github(self):
        path=filedialog.askopenfilename(parent=self,title='Open GitHub Check Runs bundle',filetypes=[('JSON','*.json'),('All files','*.*')])
        if not path:return
        try:new_data=load_github_bundle(path)
        except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as e:
            messagebox.showerror('Invalid GitHub input',str(e),parent=self);return
        self.data=new_data;self.imported=True;self.select_case(0)
        messagebox.showinfo('Check Runs loaded',
            'GitHub-shaped Check Runs imported offline. Data authenticity and historical enforcement have NOT been verified.',parent=self)

    def restore(self):
        self.data=self.original;self.imported=False;self.select_case(0)
    def show_text(self,title,content):
        win=tk.Toplevel(self);win.title(title);win.geometry('870x550');win.transient(self)
        frame=ttk.Frame(win,padding=9);frame.pack(fill='both',expand=True)
        t=tk.Text(frame,wrap='word',font=('Consolas',10),undo=False)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=t.yview)
        t.configure(yscrollcommand=scroll.set)
        t.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        t.insert('1.0',content);t.configure(state='disabled')
        return win
    def show_raw(self):
        self.show_text('Selected check evidence JSON',json.dumps(self.current_row(),indent=2,ensure_ascii=False))
    def open_policy(self):
        c=self.current_case()
        if c.get('historical_policy_provenance'):
            policy='A version-controlled policy declaration was found for this case. Historical GitHub live enforcement was not independently recovered.'
        else:
            policy='Past required-check settings were not independently recovered for this case.'
        x=(f"Case: {c['repository']} #{c['pr']}\n\n{policy}\n\n{SCOPE}\n\n"
           "The tool does not decide merge authorization. A failing selected check is a recorded outcome, not a diagnosed cause. "
           "Comparisons use exact commit subjects and selected public Check Runs, not the full GitHub history.\n\n"
           "External evidence links open only on explicit user action. Imported data is not authenticated.")
        self.show_text('Evidence scope / policy',x)
    def about(self):
        messagebox.showinfo('About VerdictLens',
            'VerdictLens V16 - plain desktop evidence inspector\n\nOffline Python/Tkinter application. GitHub Check Runs JSON import supported.\nSource-linked GitHub Check Run snapshots only.\nNo live network audit is performed.\n\n'+SCOPE,parent=self)
    def open_notes(self):
        c=self.current_case();key=c['id'];title=f"Notes - {c['repository']} #{c['pr']}"
        win=tk.Toplevel(self);win.title(title);win.geometry('760x510');win.transient(self)
        f=ttk.Frame(win,padding=9);f.pack(fill='both',expand=True)
        ttk.Label(f,text='Private analyst notes. Notes are separate from recorded evidence.').pack(anchor='w',pady=(0,6))
        txt=tk.Text(f,wrap='word',font=('Segoe UI',10));txt.pack(fill='both',expand=True)
        txt.insert('1.0',self.notes.get(key,''))
        row=ttk.Frame(f);row.pack(fill='x',pady=(7,0))
        def save():self.notes[key]=txt.get('1.0','end-1c');win.destroy()
        def export():
            self.notes[key]=txt.get('1.0','end-1c')
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',initialfile=f"VerdictLens_{c['pr']}_Notes.json",filetypes=[('JSON','*.json')])
            if path:write_json(path,{'schema':'verdictlens-v16-private-notes','case_id':key,'notes':self.notes[key],'note':'Not source evidence'})
        ttk.Button(row,text='Save for this session',command=save).pack(side='left')
        ttk.Button(row,text='Export notes JSON...',command=export).pack(side='left',padx=6)
        ttk.Button(row,text='Cancel',command=win.destroy).pack(side='right')

if __name__=='__main__':
    Inspector().mainloop()
