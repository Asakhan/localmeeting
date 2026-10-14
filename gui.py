from pathlib import Path
from datetime import datetime
import sys, os, time, subprocess, threading, html
from PySide6.QtCore import Qt, QTimer, QLockFile
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,
    QPushButton,QStackedWidget,QFrame,QTextBrowser,QListWidget,QListWidgetItem,QLineEdit,
    QComboBox,QCheckBox,QSpinBox,QDoubleSpinBox,QFormLayout,QFileDialog,QMessageBox,
    QTableWidget,QTableWidgetItem,QHeaderView,QProgressBar,QSplitter,QScrollArea)
from core import (ROOT, DATA, settings, atomic_json, read_json, new_meeting, now, stamp,
                  transcript, display, SECTIONS, export_docx, export_text)

STYLE='''
QMainWindow,QWidget {background:#F5F7F9;color:#182C37;font-family:"Malgun Gothic";font-size:13px;}
QFrame#sidebar {background:#112D32;border:0;}
QFrame#sidebar QLabel {background:transparent;color:#D8EAE7;}
QFrame#sidebar QPushButton {background:transparent;color:#BBD2D1;text-align:left;border:0;padding:15px 18px;border-radius:9px;font-size:14px;}
QFrame#sidebar QPushButton:checked {background:#245054;color:white;font-weight:bold;}
QLabel#title {font-size:29px;font-weight:bold;color:#153C3B;}
QLabel#subtitle {color:#6A7E85;font-size:13px;}
QLabel#badge {color:#257661;background:#E4F3EC;padding:7px 12px;border-radius:12px;}
QFrame#card {background:white;border:1px solid #DEE6EA;border-radius:12px;}
QFrame#card QLabel {background:transparent;}
QPushButton {background:white;border:1px solid #D4DFE4;padding:10px 17px;border-radius:7px;}
QPushButton:hover {background:#E7F2F0;}
QPushButton:disabled {color:#99A8AD;background:#EDF0F2;}
QPushButton#primary {background:#187968;color:white;border:0;font-weight:bold;}
QPushButton#primary:hover {background:#126453;}
QPushButton#danger {background:#B74E4E;color:white;border:0;}
QPushButton#danger:disabled {background:#E5DDDD;color:#AFA3A3;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:white;border:1px solid #D7E1E6;border-radius:6px;padding:8px;}
QTextBrowser,QListWidget,QTableWidget {background:white;border:1px solid #DEE6EA;border-radius:9px;padding:8px;selection-background-color:#D5EDE5;selection-color:#163B36;}
QHeaderView::section {background:#EAF0F3;border:0;padding:8px;font-weight:bold;}
QProgressBar {border:0;background:#E4EBEE;border-radius:3px;max-height:6px;}
QProgressBar::chunk {background:#2DA68A;border-radius:3px;}
'''

def label(text,name=None):
    x=QLabel(text)
    if name:x.setObjectName(name)
    x.setWordWrap(True);return x

def button(text,slot,name=None):
    x=QPushButton(text);x.clicked.connect(slot)
    if name:x.setObjectName(name)
    return x

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('로컬 회의록 · Local Minutes');self.resize(1180,800);self.setMinimumSize(960,660)
        self.config=settings();self.active=None;self.capture=None;self.worker=None;self.stage=None
        self.stop_thread=None;self.stop_error=None;self.selected=None;self.names_loading=False;self.last_live=None
        self.jobs=[];self.started_monotonic=0.;self.last_status='';self.read_mtime=None
        root=QWidget();self.setCentralWidget(root);layout=QHBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(206);nav=QVBoxLayout(sidebar);nav.setContentsMargins(18,32,18,20)
        brand=label('LOCAL\nMINUTES');brand.setStyleSheet('font-size:25px;font-weight:bold;letter-spacing:2px;');nav.addWidget(brand)
        nav.addWidget(label('대화는 편하게,\n기록은 이 PC 안에서.'));nav.addSpacing(32)
        self.nav=[];self.pages=QStackedWidget()
        for i,text in enumerate(['●  회의녹음','▤  회의록 보기','⚙  설정']):
            b=QPushButton(text);b.setCheckable(True);b.clicked.connect(lambda checked=False,n=i:self.navigate(n));nav.addWidget(b);self.nav.append(b)
        nav.addStretch();nav.addWidget(label('OFFLINE FIRST\n음성·회의록 외부 전송 없음'))
        layout.addWidget(sidebar);layout.addWidget(self.pages,1)
        self.build_recording();self.build_library();self.build_settings();self.navigate(0)
        self.statusBar().showMessage('준비됨 · 녹음이 끝나면 회의록과 전체 전사를 저장합니다.')
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(500)

    def showEvent(self,event):
        super().showEvent(event)
        if not getattr(self,'placed',False):
            self.placed=True
            # Windows can apply its first monitor-DPI transition after construction.
            QTimer.singleShot(50,self.fit_window)

    def fit_window(self):
        screen=self.screen().availableGeometry()
        self.resize(max(960,min(1180,screen.width()-60)),max(660,min(800,screen.height()-60)))

    def page(self,title,subtitle):
        w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(30,28,30,24);v.setSpacing(16)
        header=QHBoxLayout();titles=QVBoxLayout();titles.addWidget(label(title,'title'));titles.addWidget(label(subtitle,'subtitle'))
        header.addLayout(titles,1);header.addWidget(label('●  로컬 전용','badge'),0,Qt.AlignTop);v.addLayout(header);self.pages.addWidget(w)
        return w,v

    def build_recording(self):
        w,v=self.page('회의녹음','녹음을 시작하면 발언을 기록하고, 종료하면 회의록을 자동 작성합니다.')
        card=QFrame();card.setObjectName('card');c=QHBoxLayout(card);c.setContentsMargins(22,18,22,18)
        info=QVBoxLayout();self.clock_label=label('00:00:00');self.clock_label.setStyleSheet('font-size:36px;font-weight:bold;')
        self.record_status=label('회의를 시작할 준비가 되었습니다.','subtitle');info.addWidget(self.clock_label);info.addWidget(self.record_status);c.addLayout(info,1)
        self.start_button=button('●  회의 녹음 시작',self.start_recording,'primary');self.stop_button=button('■  회의 종료',self.stop_recording,'danger');self.stop_button.setEnabled(False)
        c.addWidget(self.start_button);c.addWidget(self.stop_button);v.addWidget(card)
        self.level=QProgressBar();self.level.setRange(0,100);self.level.setTextVisible(False);v.addWidget(self.level)
        heading=QHBoxLayout();heading.addWidget(label('실시간 발언','subtitle'));heading.addStretch();self.speaker_count=label('감지된 화자 0명','subtitle');heading.addWidget(self.speaker_count);v.addLayout(heading)
        self.live=QTextBrowser();self.live.setPlaceholderText('이곳에 시간과 화자별 발언이 표시됩니다.\n\n발언은 약 12초 단위로 분석합니다.\n짧은 발언이나 동시에 말한 구간은 화자 확인이 필요할 수 있습니다.');v.addWidget(self.live,1)
        v.addWidget(label('회의록 + 전체전사.txt 저장 확인 후 오디오는 자동 삭제됩니다. 오류 시에는 재처리를 위해 보존합니다.','subtitle'))

    def build_library(self):
        w,v=self.page('회의록 보기','회의록을 확인하고 참석자 이름을 입력하세요. 전체 문서에 함께 반영됩니다.')
        top=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('회의 제목 검색');self.search.textChanged.connect(self.refresh_library)
        top.addWidget(self.search,1);top.addWidget(button('폴더 열기',lambda:self.open_path(self.config['folder'])));top.addWidget(button('새로고침',self.refresh_library));v.addLayout(top)
        split=QSplitter();self.meetings=QListWidget();self.meetings.setMinimumWidth(190);self.meetings.setWordWrap(True);self.meetings.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.meetings.currentItemChanged.connect(self.select_meeting);split.addWidget(self.meetings)
        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(0,0,0,0);self.preview=QTextBrowser();rv.addWidget(self.preview,1)
        self.names=QTableWidget(0,2);self.names.setHorizontalHeaderLabels(['감지된 화자','실제 이름']);self.names.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.names.setMaximumHeight(120);rv.addWidget(self.names)
        actions=QHBoxLayout();self.rename_button=button('이름 적용',self.save_names);self.word_button=button('Word 열기',self.open_word);self.txt_button=button('전체 전사',self.open_text);self.retry_button=button('다시 처리',self.retry)
        for b in [self.rename_button,self.word_button,self.txt_button,self.retry_button]:actions.addWidget(b)
        rv.addLayout(actions);split.addWidget(right);split.setSizes([260,620]);v.addWidget(split,1)

    def build_settings(self):
        self.settings_page,v=self.page('설정','회의 환경에 필요한 항목만 설정합니다. 저장된 설정은 다음 회의부터 적용됩니다.')
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
        form_widget=QWidget();form=QFormLayout(form_widget);form.setSpacing(16);form.setContentsMargins(0,4,12,4)
        scroll.setWidget(form_widget)
        row=QHBoxLayout();self.folder_edit=QLineEdit(self.config['folder']);row.addWidget(self.folder_edit,1);row.addWidget(button('찾아보기',self.choose_folder));form.addRow('회의록 저장 폴더',row)
        self.language=QComboBox();self.language.addItem('한국어 전용 · 한국어 특화 Whisper', 'ko');self.language.addItem('한국어 + English · Whisper large-v3','mixed');self.language.setCurrentIndex(0 if self.config['language']=='ko' else 1);form.addRow('회의 언어',self.language)
        self.mic=QComboBox();self.mic.addItem('Windows 기본 마이크',-1)
        try:
            from capture import devices
            for d in devices():
                if not d.get('isLoopbackDevice'):self.mic.addItem(d['name'],d['index'])
        except Exception as e:self.statusBar().showMessage('오디오 장치 확인: '+str(e))
        ix=self.mic.findData(self.config['microphone']);self.mic.setCurrentIndex(max(0,ix));form.addRow('마이크',self.mic)
        self.system_audio=QCheckBox('컴퓨터에서 재생되는 상대방 음성도 녹음');self.system_audio.setChecked(self.config['system_audio']);form.addRow('온라인 회의',self.system_audio)
        form.addRow('',label('온라인 회의에서는 헤드폰을 사용하면 스피커 소리가 마이크에 중복 녹음되는 것을 줄일 수 있습니다.','subtitle'))
        self.glossary=QLineEdit(self.config['glossary']);self.glossary.setPlaceholderText('예: 노우버스, 프로젝트명, 전문 용어 (쉼표로 구분)');self.glossary.setMaxLength(500);form.addRow('자주 쓰는 용어',self.glossary)
        self.threads=QSpinBox();self.threads.setRange(2,6);self.threads.setValue(self.config['threads']);form.addRow('분석 CPU 스레드',self.threads)
        self.device=QComboBox();self.device.addItem('자동 · GPU 우선, 여유 부족 시 CPU','auto');self.device.addItem('CPU만 사용','cpu');self.device.setCurrentIndex(1 if self.config['device']=='cpu' else 0);form.addRow('처리 장치',self.device)
        self.threshold=QDoubleSpinBox();self.threshold.setRange(.4,.85);self.threshold.setSingleStep(.05);self.threshold.setValue(self.config['speaker_threshold']);form.addRow('화자 구분 민감도',self.threshold)
        form.addRow('',label('화자가 너무 많이 나뉘면 값을 낮추고, 다른 사람이 합쳐지면 높이세요. 이름 수정은 회의록 보기에서 가능합니다.','subtitle'))
        for widget in [self.folder_edit,self.language,self.mic,self.glossary,self.threads,self.device,self.threshold]:widget.setMinimumHeight(36)
        v.addWidget(scroll,1);self.model_status=label('','subtitle');v.addWidget(self.model_status)
        v.addWidget(button('설정 저장',self.save_settings,'primary'),alignment=Qt.AlignRight)

    def navigate(self,index):
        self.pages.setCurrentIndex(index)
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        if index==1:self.refresh_library()
        if index==2:
            self.settings_page.setEnabled(self.active is None)
            missing=self.missing_models(self.config)
            self.model_status.setText('오프라인 모델 준비 완료 · 녹음 중에는 회의록 모델을 실행하지 않습니다.' if not missing else '누락된 모델: '+', '.join(missing))

    def missing_models(self,config):
        root=Path(config['model_root']);names=['komix/model.bin','komix/tokenizer.json','large-v3/model.bin','speaker.onnx','segmentation.onnx','llm/Qwen3.5-9B-Q4_K_M.gguf']
        return [name for name in names if not (root/name).exists()]

    def choose_folder(self):
        path=QFileDialog.getExistingDirectory(self,'회의록 저장 폴더',self.folder_edit.text())
        if path:self.folder_edit.setText(path)

    def save_settings(self):
        try:
            folder=Path(self.folder_edit.text()).expanduser()
            if not folder.is_absolute():raise ValueError('저장 폴더는 절대 경로로 지정하세요.')
            folder.mkdir(parents=True,exist_ok=True)
            self.config.update(folder=str(folder),language=self.language.currentData(),microphone=self.mic.currentData(),
                system_audio=self.system_audio.isChecked(),threads=self.threads.value(),device=self.device.currentData(),
                glossary=self.glossary.text(),speaker_threshold=self.threshold.value())
            atomic_json(DATA/'settings.json',self.config);self.statusBar().showMessage('설정을 저장했습니다.')
        except Exception as e:self.error(str(e))

    def launch_worker(self,stage):
        from winjob import Job
        args=[sys.executable]
        if not getattr(sys,'frozen',False):args.append(str(ROOT/'app.py'))
        args += ['--'+stage,str(self.active)]
        self.worker_log=(self.active/f'{stage}_process.log').open('a',encoding='utf-8')
        self.worker=subprocess.Popen(args,stdout=self.worker_log,stderr=self.worker_log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job=Job();job.assign(self.worker);self.jobs.append(job)
        except Exception:
            self.worker.terminate();self.worker.wait();self.worker=None;self.worker_log.close();raise
        self.stage=stage

    def start_recording(self):
        if self.active:return
        missing=self.missing_models(self.config)
        if missing:self.error('로컬 모델 파일이 없습니다: '+', '.join(missing));return
        try:
            from capture import Capture
            self.active=new_meeting(dict(self.config));self.capture=Capture(self.active,self.config)
            self.capture.start();self.started_monotonic=self.capture.started
            self.start_button.setEnabled(False);self.stop_button.setEnabled(True);self.last_live=None;self.live.clear()
            self.launch_worker('transcribe');self.record_status.setText('녹음 중 · 음성 모델 준비 중');self.stop_thread=None
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
        except Exception as e:
            if self.capture:
                try:self.capture.stop()
                except Exception:pass
            self.active=None;self.capture=None;self.start_button.setEnabled(True);self.stop_button.setEnabled(False);self.error(str(e))

    def stop_recording(self):
        if not self.capture or self.stop_thread:return
        self.stop_button.setEnabled(False);self.record_status.setText('녹음을 마치고 남은 발언을 정리합니다.')
        meta=read_json(self.active/'meeting.json',{});meta.update(ended=now(),state='processing');atomic_json(self.active/'meeting.json',meta)
        self.stop_error=None
        def finish():
            try:self.capture.stop()
            except Exception as e:self.stop_error=str(e)
        self.stop_thread=threading.Thread(target=finish,daemon=True);self.stop_thread.start()

    def tick(self):
        if self.capture:
            if self.stop_thread is None:self.clock_label.setText(stamp(time.monotonic()-self.started_monotonic))
            self.level.setValue(int(max(self.capture.levels.values(),default=0)*100))
            if self.capture.errors and self.stop_thread is None:
                self.statusBar().showMessage('녹음 오류: '+'; '.join(self.capture.errors));self.stop_recording()
            if self.stop_thread and not self.stop_thread.is_alive():
                self.capture=None;self.stop_thread=None;self.level.setValue(0)
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                if self.stop_error:
                    self.error(self.stop_error);self.finish_active(False);return
                if self.worker is None:self.finish_active(False);return
        if self.active:
            status=read_json(self.active/'worker_status.json',{})
            message=status.get('message','녹음 중')
            self.record_status.setText(message);self.statusBar().showMessage(message)
            path=self.active/'transcript.jsonl'
            if path.exists():
                mt=path.stat().st_mtime_ns
                if mt!=self.last_live:
                    self.last_live=mt;rows=transcript(self.active);self.render_transcript(rows[-200:])
                    self.speaker_count.setText(f"감지된 화자 {len({r['speaker'] for r in rows if r['speaker'].startswith('참석자')})}명 (추정)")
            if self.worker and self.worker.poll() is not None:
                code=self.worker.returncode;stage=self.stage;self.worker=None;self.worker_log.close()
                for job in self.jobs:job.close()
                self.jobs=[]
                if code!=0:
                    if self.capture:
                        self.record_status.setText('분석 중단 · 녹음은 계속됩니다. 종료 후 다시 처리할 수 있습니다.')
                        # Show once; recording persists independently.
                        self.error(status.get('message','음성 분석 프로세스 오류'))
                    else:self.finish_active(False)
                elif stage=='transcribe':
                    try:self.launch_worker('summarize')
                    except Exception as e:self.error(str(e));self.finish_active(False)
                else:self.finish_active(True)

    def finish_active(self,success):
        if self.worker and self.worker.poll() is None:
            for job in self.jobs:job.close()
            self.jobs=[];self.worker.wait(timeout=10);self.worker=None;self.worker_log.close()
        if self.active:
            meta=read_json(self.active/'meeting.json',{})
            if not success:
                meta['state']='error';atomic_json(self.active/'meeting.json',meta)
                export_text(self.active)
            self.selected=self.active
        self.active=None;self.start_button.setEnabled(True);self.stop_button.setEnabled(False)
        self.record_status.setText('회의록과 전체 전사가 저장되었습니다.' if success else '처리가 완료되지 않았습니다. 회의록 보기에서 다시 처리하세요.')
        self.navigate(1)

    def render_transcript(self,rows):
        colors=['#167D70','#4E68A5','#9654A1','#BC752D']
        parts=[]
        for row in rows:
            speaker=row['speaker'];i=int(speaker[3:])-1 if speaker.startswith('참석자') else 0
            parts.append(f'<p style="margin:12px 0"><span style="color:#8A9AA3">{stamp(row["start"])}</span> &nbsp; <b style="color:{colors[i%4]}">{html.escape(speaker)}</b><br>{html.escape(row["text"])}</p>')
        bar=self.live.verticalScrollBar();bottom=bar.value()>=bar.maximum()-30
        self.live.setHtml(''.join(parts))
        if bottom:bar.setValue(bar.maximum())

    def refresh_library(self):
        chosen=str(self.selected) if self.selected else None;self.meetings.blockSignals(True);self.meetings.clear()
        root=Path(self.config['folder']);query=self.search.text().strip().lower()
        if root.exists():
            for p in sorted(root.glob('*/meeting.json'),reverse=True):
                meta=read_json(p,{});minutes=read_json(p.parent/'minutes.json',{})
                title=minutes.get('title','정리 중인 회의' if meta.get('state')=='processing' else '회의 기록')
                if query and query not in (title+p.parent.name).lower():continue
                state={'complete':'완료','error':'재처리 필요','recording':'녹음/복구 대기','processing':'처리 중','review':'확인 필요'}.get(meta.get('state'),'확인 필요')
                item=QListWidgetItem(f'{title}\n{meta.get("started","")[:16].replace("T"," ")} · {state}');item.setData(Qt.UserRole,str(p.parent));self.meetings.addItem(item)
                if str(p.parent)==chosen:self.meetings.setCurrentItem(item)
        self.meetings.blockSignals(False)
        if self.meetings.currentRow()<0 and self.meetings.count():self.meetings.setCurrentRow(0)
        else:self.select_meeting(self.meetings.currentItem())

    def select_meeting(self,item,*args):
        if not item:
            self.selected=None;self.preview.setPlainText('저장된 회의록이 없습니다.');self.names.setRowCount(0);return
        self.selected=Path(item.data(Qt.UserRole));meta=read_json(self.selected/'meeting.json',{})
        names=read_json(self.selected/'names.json',{});minutes=display(read_json(self.selected/'minutes.json',{}),names)
        rows=transcript(self.selected);speakers=sorted({r['speaker'] for r in rows if r['speaker'].startswith('참석자')},key=lambda s:int(s[3:]))
        self.names.setRowCount(len(speakers))
        for i,s in enumerate(speakers):
            cell=QTableWidgetItem(s);cell.setFlags(cell.flags() & ~Qt.ItemIsEditable);self.names.setItem(i,0,cell);self.names.setItem(i,1,QTableWidgetItem(names.get(s,'')))
        content=f'<h2>{html.escape(minutes.get("title","회의 기록"))}</h2><p>{html.escape(meta.get("started",""))} ~ {html.escape(meta.get("ended") or "종료 미확인")}</p>'
        content+=f'<p>감지된 화자 {len(speakers)}명 (추정) · '+html.escape(', '.join(names.get(s,s) for s in speakers))+'</p>'
        if not minutes:content+='<p>회의록 작성이 완료되지 않았습니다. 아래 다시 처리 버튼으로 복구할 수 있습니다.</p>'
        if minutes.get('note'):content+='<p>'+html.escape(minutes['note'])+'</p>'
        for key,title in SECTIONS:
            content+='<h3>'+title+'</h3><ul>'
            for entry in minutes.get(key,[]) or ['발언에서 확인되지 않음']:
                if isinstance(entry,dict):entry=f"{entry.get('owner','미정')} · {entry.get('due','미정')} · {entry.get('task','')}"
                content+='<li>'+html.escape(str(entry))+'</li>'
            content+='</ul>'
        self.preview.setHtml(content)
        busy=self.active is not None
        self.retry_button.setEnabled(not busy);self.rename_button.setEnabled(not busy)

    def save_names(self):
        if not self.selected or self.active:return
        try:
            names={self.names.item(i,0).text():self.names.item(i,1).text().strip() for i in range(self.names.rowCount()) if self.names.item(i,1).text().strip()}
            atomic_json(self.selected/'names.json',names);export_text(self.selected)
            if (self.selected/'minutes.json').exists():
                doc=export_docx(self.selected);meta=read_json(self.selected/'meeting.json',{});meta['docx']=doc.name;atomic_json(self.selected/'meeting.json',meta)
            self.select_meeting(self.meetings.currentItem());self.statusBar().showMessage('이름을 회의록과 전체 전사에 일괄 반영했습니다.')
        except Exception as e:self.error(str(e))

    def retry(self):
        if self.active or not self.selected:return
        try:
            from capture import recover_partial
            folder=self.selected;meta=read_json(folder/'meeting.json',{})
            # Retry uses current installed model location, preserves meeting language.
            meta['config'].update(model_root=self.config['model_root'],threads=self.config['threads'],device=self.config['device'])
            meta['ended']=meta.get('ended') or datetime.fromtimestamp((folder/'meeting.json').stat().st_mtime).astimezone().isoformat(timespec='seconds')
            if not (folder/'capture_done.json').exists():
                recover_partial(folder);atomic_json(folder/'capture_done.json',dict(ended=meta['ended'],errors=['비정상 종료에서 복구됨: 녹음 누락 여부를 확인하세요.']))
            meta['state']='processing';atomic_json(folder/'meeting.json',meta)
            self.active=folder;self.last_live=None;self.start_button.setEnabled(False)
            audio=any((folder/'audio').glob('*.wav'))
            if not audio and not transcript(folder):raise RuntimeError('재처리할 음성이나 전사가 없습니다.')
            self.launch_worker('transcribe' if audio else 'summarize');self.navigate(0)
        except Exception as e:self.active=None;self.start_button.setEnabled(True);self.error(str(e))

    def open_path(self,path):
        try:
            path=Path(path)
            if not path.exists():raise FileNotFoundError('파일이 아직 생성되지 않았습니다: '+str(path))
            os.startfile(str(path))
        except Exception as e:self.error(str(e))
    def open_word(self):
        if self.selected:self.open_path(self.selected/read_json(self.selected/'meeting.json',{}).get('docx','회의록.docx'))
    def open_text(self):
        if self.selected:
            try:self.open_path(export_text(self.selected))
            except Exception as e:self.error(str(e))
    def error(self,text):QMessageBox.warning(self,'확인 필요',text)
    def closeEvent(self,event):
        if self.active:
            QMessageBox.information(self,'회의 진행 중','회의 종료 후 저장이 완료될 때 창을 닫아주세요. 창을 최소화하고 다른 작업을 할 수 있습니다.')
            event.ignore();return
        for job in self.jobs:job.close()
        event.accept()

def run_gui():
    app=QApplication(sys.argv);app.setApplicationName('LocalMinutes');app.setFont(QFont('Malgun Gothic',10));app.setStyleSheet(STYLE)
    DATA.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(DATA/'app.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None,'로컬 회의록','프로그램이 이미 실행 중입니다.');return 0
    window=Window();window.show()
    if '--smoke' in sys.argv:
        def snapshot():
            target=ROOT/'test-output';target.mkdir(exist_ok=True);window.grab().save(str(target/'gui.png'))
            app.quit()
        QTimer.singleShot(2000,snapshot)
    result=app.exec();lock.unlock();return result
