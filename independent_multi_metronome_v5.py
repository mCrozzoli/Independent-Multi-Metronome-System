'''
BUGS.
3. Tkinter window too slow to load changes.

'''


import time
import mido
import numpy as np
from numpy import interp
from IPython.display import clear_output
from threading import Thread
import random
import tkinter as tk
import asyncio
import simpleaudio as sa

class MIDIDispatcher(Thread):
    
    def __init__(self, inport):
        super().__init__()
        self.inport = inport
        self.latest_msgs = {}
        self.cc_map = {}
        self.running = False
    
    def register(self, receiver_id, receiver_cc_map):
        '''
        Register a midi receiver:
        - receiver_id: like 0, 'id0' or whatever
            note: special id '*' means master (send to all receivers)
        - receiver_cc_map: dict {'message_key': cc_num, ...} like {'vol': 7, ...}
        '''
        self.latest_msgs[receiver_id] = {}
        for key, cc in receiver_cc_map.items():
            # for now we assume that there is only one receiver for every CC
            if cc in self.cc_map:
                print(f"Warning: overwriting mapping for CC {cc}")
                print(f"old recv_id: {self.cc_map[cc][0]}, key: {self.cc_map[cc][1]}")
                print(f"new recv_id: {receiver_id}, key: {key}")
            self.cc_map[cc] = [receiver_id, key]
        
    def on_msg(self, msg):
        cc = msg.control
        if cc not in self.cc_map:
            return
        
        recv_id, msg_key = self.cc_map[cc]
        if recv_id == '*':
            all_recv_ids = self.latest_msgs.keys()
            for recv_id in all_recv_ids:
                 self.latest_msgs[recv_id][msg_key] = msg
        else:
            self.latest_msgs[recv_id][msg_key] = msg
            
    def get_messages(self, receiver_id, flush=True):
        msgs = self.latest_msgs[receiver_id].copy()
        if flush:
            self.latest_msgs[receiver_id] = {}
        return msgs
    
    def run(self):
        self.running = True
        while self.running:
            msg = self.inport.receive()
            self.on_msg(msg)
            
    def stop(self):
        self.running = False

class Metronome():
    global master_controls
    global metronomes_controls

    def __init__(self, midi_dispatcher, inst_number, vol_beat=1, tempo=60, active=True, min_tempo = 20, max_tempo = 200, beat_freq = 1000, beat_dur = 0.1):
        self.midi_dispatcher = midi_dispatcher
        self.inst_number = inst_number
        self.tempo = tempo
        self.active = active
        self.on_off_list = ['ON','OFF','OFF','ON']
        self.selector = 0
        self.tapped_list = []
        self.tapped_tempo = 0
        self.sync_on_off = ['OFF','ON','ON','OFF']
        self.sync_on_off_selector = 0
        #selecting specific MIDI controls for this metronome
        self.controls = {key: val[self.inst_number] for key, val in metronomes_controls.items()}
        self.midi_dispatcher.register(self.inst_number, self.controls)
        self.min_tempo = min_tempo
        self.max_tempo = max_tempo
        self.vol_beat = vol_beat
        self.min_vol = 0.01
        self.max_vol = 1
        self.beat_freq = beat_freq #possible dev. change pitch for each metronome.
        self.beat_dur = beat_dur #possible development of the code, change duration of the beat
        self.fs = 44100 #sampling size
        self.t = np.linspace(0, self.beat_dur, int(self.beat_dur*self.fs), False) 
        self.note = np.sin(self.beat_freq *self.t *2 *np.pi)
        self.audio = self.note*(2**15-1) / np.max(np.max(self.note)) #16 bit conversion
        self.audio = self.audio.astype(np.int16)
        self.beat_sound = sa.WaveObject(self.audio,1,2,self.fs)
        
    def __str__(self):
        return f"Instrument number: {self.inst_number}\nTempo: {self.tempo}\n"
   
    def beat(self):
        if self.active:
            self.beat_sound.play()
            time.sleep(60/self.tempo)
        self.update()
            
    def set_volume(self, b_sound, v_beat):
        if v_beat < 0:
            v_beat = self.min_vol
        if v_beat > 1:
            v_beat = self.max_vol
        audio_data = np.frombuffer(b_sound.audio_data, dtype=np.int16)
        volume_factor = v_beat * 32767 / np.max(np.abs(audio_data))
        audio_data = np.int16(audio_data * volume_factor)
        self.beat_sound = sa.WaveObject(audio_data, b_sound.num_channels, b_sound.bytes_per_sample, b_sound.sample_rate)
    
    def tap_tempo(self):
        tapped_tempo_list = self.tapped_list[:-6:-1] #just save at least the last 5 inputs 
        tapped_tempo_list.reverse()
        self.tapped_tempo = (60*len(tapped_tempo_list)) / (tapped_tempo_list[-1] - tapped_tempo_list[0])
        
    def tap_me(self):
        self.tempo = int(self.tapped_tempo)
        print(f'The estimated tempo is {self.tapped_tempo} BPM.')
        self.tapped_list = [] #cleaning the original
    
    def select_to_sync(self):
        sync_list.add(self.inst_number)
        sync_tempo_list.add(self.tempo)
        print(f"selected to sync: {sync_list}")
        print(f"List of tempos to sync: {sync_tempo_list}")
        
    def unselect_to_sync(self):
        sync_list.remove(self.inst_number)
        try:
            sync_tempo_list.remove(self.tempo)
        except:
            print('Tempo to unselect not on list')
        print(f"selected to sync: {sync_list}")
        print(f"List of tempos to sync: {sync_tempo_list}")
              
    def sync_max(self):
        if len(sync_tempo_list) != 0:
            return max(sync_tempo_list)
    def sync_min(self):
        if len(sync_tempo_list) != 0:
            return min(sync_tempo_list)
    def sync_avg(self):
        if len(sync_tempo_list) != 0:
            return np.mean(list(sync_tempo_list))
    def sync_rand(self):
        if len(sync_tempo_list) != 0:
            selector = random.randrange(len(sync_tempo_list))
            return list(sync_tempo_list)[selector]
        
    def sync_me(self, new_tempo):
        self.tempo = new_tempo
        sync_list.remove(self.inst_number)
        if len(sync_list) == 0:
            self.clear_sync_q()
                
    def clear_sync_q(self):
        sync_list.clear()
        sync_tempo_list.clear()
        self.sync_on_off_selector = 0 #fixing bug to unselect after hard cleaning func
        print(f"Sync Queu Clear: {sync_list} | {sync_tempo_list}")

    
    def update(self):
        global sync_list
        global sync_tempo_list
        global sync_selector
        global sync_mode_selector
        global sync_mode_selected
        global master_tempo
        global master_onoff
        global master_vol
        global master_tap
        global master_select
        
        latest_messages = self.midi_dispatcher.get_messages(self.inst_number)
        
        for key, msg in latest_messages.items():
            if key == 'tempo_knob':
                self.tempo = int(interp(msg.value,[0,127],[self.min_tempo,self.max_tempo]))
                #clear_output()
                print(f"Inst: {self.inst_number} Tempo: {self.tempo}", end='\r')
                if msg.control == 23:
                    master_tempo = int(interp(msg.value,[0,127],[self.min_tempo,self.max_tempo]))
  
            elif key == 'tap_button':
                self.tapped_list.append(time.time())
                try:
                    self.tap_tempo()
                except:
                    continue
                if msg.control == 71:
                    master_tap = self.tapped_tempo                    
            
            elif key == 'tap_metronome':
                if self.tapped_list != []:
                    self.tap_me()
                else:
                    print('Empty tap tempo list')
                print(f"Metronome number: {self.inst_number} | Tempo: {self.tempo}\n", end='\r')
            
            elif key == 'vol_slide':
                self.vol_beat = interp(msg.value,[0,127],[self.min_vol,self.max_vol])
                self.set_volume(self.beat_sound, self.vol_beat)
                clear_output()
                print(f"Inst: {self.inst_number} vol: {self.vol_beat*100}")
                if msg.control == 7:
                    master_vol = self.vol_beat
                    
            elif key == 'play_stop':
                self.selector += 1
                if self.selector >3:
                    self.selector = 0
                if 'ON' in self.on_off_list[self.selector]:
                    clear_output()
                    print(f"Inst: {self.inst_number} 'ON'")
                    self.active = True
                if 'OFF' in self.on_off_list[self.selector]:
                    clear_output()
                    print(f"Inst: {self.inst_number} 'OFF'")
                    self.active = False
                if msg.control == 39:
                    if master_onoff == False:
                        master_onoff = True
                    else:
                        master_onoff = False
                
            elif key == 'sync_select':
                self.sync_on_off_selector += 1
                if self.sync_on_off_selector >3:
                    self.sync_on_off_selector = 0
                try:
                    if 'ON' in self.sync_on_off[self.sync_on_off_selector]:
                        self.select_to_sync()
                    elif 'OFF' in self.sync_on_off[self.sync_on_off_selector]:
                        self.unselect_to_sync()
                except:
                    continue
                if msg.control == 55:
                    if master_select == False:
                        master_select = True
                    else:
                        master_select = False
                    
            elif key == 'sync_mode_plus':
                sync_selector += 1
                if sync_selector > 6:
                    sync_selector = 6
                sync_mode_selected = sync_mode_selector[sync_selector]
                print(f"Sync Mode: {sync_mode_selected}", end='r')
            elif key == 'sync_mode_minus':
                sync_selector -= 1
                if sync_selector < 0:
                    sync_selector = 0
                sync_mode_selected = sync_mode_selector[sync_selector]
                print(f"Sync Mode: {sync_mode_selected}", end='r')
                
            elif key == 'sync_selected':
                if self.inst_number in sync_list:
                    if sync_mode_selected == 'MAX':
                        tempo = self.sync_max()
                        self.sync_me(tempo)
                    elif sync_mode_selected == 'MIN':
                        tempo = self.sync_min()
                        self.sync_me(tempo)
                    elif sync_mode_selected == 'AVG':
                        tempo = self.sync_avg()
                        self.sync_me(tempo)
                    elif sync_mode_selected == 'RAND':
                        tempo = self.sync_rand()
                        self.sync_me(tempo)
                print(f"Metronome number: {self.inst_number} | Tempo: {self.tempo}\n") #, end='\r')
                
            elif key == 'clear_sync_q':
                self.clear_sync_q()

def update_tk(arg, frame, var_tempo, metronomes):
    global sync_mode_selected #dysplay sync mode
    global sync_list #display sync q
    global master_tempo
    global master_onoff
    global master_vol
    global master_tap
    global master_select
    
    tempos = []
    actives = []
    volumes = []
    sync_me = []
    tapped_tempos = []
    
    for metronome in metronomes:
        tempos.append(metronome.tempo)
        tapped_tempos.append(metronome.tapped_tempo)
        if metronome.active == True:
            actives.append('On')
        else:
            actives.append('Off')
        volumes.append(metronome.vol_beat)
        
        if metronome.inst_number in sync_list:
            sync_me.append('Sync me')
        else:
            sync_me.append(' ')
        
    display_s_mode = sync_mode_selected
    display_s_q = sync_list
    
    col=8 #column for master controls. Last column in the grid
            
    for metronome in range(len(metronomes)):
        #general ctrls
        gen_ctrl_col = tk.Label(frame, text=f"Sync Mode: {display_s_mode}", font=(font_gen_sub, font_gen_size_s), bg=bg_gen_col, fg=fg_gen_col)
        gen_ctrl_col.grid(row=5, column=0)
        gen_ctrl_col = tk.Label(frame, text=f"Sync: {display_s_q}", font=(font_gen_sub, font_gen_size_s), bg=bg_gen_col, fg=fg_gen_col)
        gen_ctrl_col.grid(row=6, column=0, sticky=tk.W+tk.E)
        #metronomes' ctrls
        var_tempo = tk.Label(frame, text=f't. {tempos[metronome]}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_tempo.grid(row=1, column=metronome+1)
        var_active = tk.Label(frame, text=f'{actives[metronome]}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_active.grid(row=2, column=metronome+1, sticky=tk.W+tk.E)
        var_vol = tk.Label(frame, text=f'v. {int(volumes[metronome]*100)}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_vol.grid(row=3, column=metronome+1, sticky=tk.W+tk.E)
        var_select = tk.Label(frame, text=f'{sync_me[metronome]}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_select.grid(row=5, column=metronome+1, sticky=tk.W+tk.E)
        var_tap_tempo = tk.Label(frame, text=f'{int(tapped_tempos[metronome])}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_tap_tempo.grid(row=9, column=metronome+1, sticky=tk.W+tk.E)
        #Master controls
        master_vat_tempo = tk.Label(frame, text=f't. {master_tempo}', font=(font_master_sub, font_master_size_s), bg=bg_master_colour, fg=fg_master_colour)
        master_vat_tempo.grid(row=1, column=col)
        master_var_active = tk.Label(frame, text=f'On/Off', font=(font_master_sub, font_master_size_s), bg=bg_m_onoff_col, fg=fg_master_colour)
        master_var_active.grid(row=2, column=col, sticky=tk.W+tk.E)
        master_var_vol = tk.Label(frame, text=f'v. {int(master_vol)*100}', font=(font_master_sub, font_master_size_s), bg=bg_master_colour, fg=fg_master_colour)
        master_var_vol.grid(row=3, column=col, sticky=tk.W+tk.E)
        master_var_select = tk.Label(frame, text=f'Un-Select', font=(font_master_sub, font_master_size_s), bg=bg_m_select_col, fg=fg_master_colour)
        master_var_select.grid(row=5, column=col, sticky=tk.W+tk.E)
        master_var_tap = tk.Label(frame, text=f'tap. {int(master_tap)}', font=(font_master_sub, font_master_size_s), bg=bg_master_colour, fg=fg_master_colour)
        master_var_tap.grid(row=9, column=col, sticky=tk.W+tk.E)
    
    arg.after(1000, lambda: update_tk(arg, frame, var_tempo, metronomes))

def tkinter_ui(metronomes):
    global sync_mode_selected #dysplay sync mode
    global sync_list #display sync q
    global sync_tempo_list #display sync q
    global master_tempo
    global master_onoff
    global master_vol
    global master_tap
    global master_select
    
    tempos = [0] *len(metronomes)
    actives = ['On'] *len(metronomes)
    volumes = [1] *len(metronomes)
    sync_me = ['_'] *len(metronomes)
    tapped_tempos = [0] *len(metronomes)
    display_s_mode = sync_mode_selected
    display_s_q = sync_list
    
    root = tk.Tk()
    root.title('Independent Multi Metronome')
    root.eval("tk::PlaceWindow . left") #center #right #topleft
    frame = tk.Frame(root, bg=bg_colour)

    for i in range(len(metronomes)+3):
        frame.columnconfigure(i, minsize=100, pad=50)
    
    #Create the row configuration for every column. 3 types: gen control, metronome, and master control
    #General controls column
    gen_ctrl_col = tk.Label(frame, text='Gen', font=(font_gen, font_gen_size), bg=bg_gen_col, fg=fg_gen_col)
    gen_ctrl_col.grid(row=0, column=0, sticky=tk.W+tk.E)
    gen_ctrl_col = tk.Label(frame, text=f"Sync: {display_s_q}", font=(font_gen_sub, font_gen_size_s), bg=bg_gen_col, fg=fg_gen_col)
    gen_ctrl_col.grid(row=5, column=0, sticky=tk.W+tk.E)
    gen_ctrl_col = tk.Label(frame, text=f"{display_s_mode}", font=(font_gen_sub, font_gen_size_s), bg=bg_gen_col, fg=fg_gen_col)
    gen_ctrl_col.grid(row=6, column=0, sticky=tk.W+tk.E)
    
    for i in range(len(metronomes)):
        var_name = tk.Label(frame, text=f'm.{i+1}', bg=bg_colour, fg=fg_colour, font=(font_main, font_size_m))
        var_name.grid(row=0, column=i+1)
        var_tempo = tk.Label(frame, text=f't. {tempos[i]}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_tempo.grid(row=1, column=i+1)
        var_active = tk.Label(frame, text=f'{actives[i]}', font=(font_sub, font_size_s))
        var_active.grid(row=2, column=i+1, sticky=tk.W+tk.E)
        var_vol = tk.Label(frame, text=f'v. {int(volumes[i]*100)}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_vol.grid(row=3, column=i+1, sticky=tk.W+tk.E)
        var_select = tk.Label(frame, text=f'{sync_me[i]}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_select.grid(row=5, column=i+1, sticky=tk.W+tk.E)
        var_tap_tempo = tk.Label(frame, text=f'{int(tapped_tempos[i])}', bg=bg_colour, fg=fg_colour, font=(font_sub, font_size_s))
        var_tap_tempo.grid(row=9, column=i+1, sticky=tk.W+tk.E)
        
    #Master controls ()
    col = 8 #last row of the midi controller
    master_ctrl_col = tk.Label(frame, text='Ma', bg=bg_master_colour, fg=fg_master_colour, font=(font_master, font_master_size))
    master_ctrl_col.grid(row=0, column=col)
    master_vat_tempo = tk.Label(frame, text=f't. {master_tempo}', bg=bg_master_colour, fg=fg_master_colour, font=(font_master_sub, font_master_size_s))
    master_vat_tempo.grid(row=1, column=col, sticky=tk.W+tk.E)
    master_var_active = tk.Label(frame, text=f'{master_onoff}', bg=bg_master_colour, fg=fg_master_colour, font=(font_master_sub, font_master_size_s))
    master_var_active.grid(row=2, column=col, sticky=tk.W+tk.E)
    master_var_vol = tk.Label(frame, text=f'v. {int(master_vol)*100}', bg=bg_master_colour, fg=fg_master_colour, font=(font_master_sub, font_master_size_s))
    master_var_vol.grid(row=3, column=col, sticky=tk.W+tk.E)
    master_var_select = tk.Label(frame, text=f'{master_select}', bg=bg_master_colour, fg=fg_master_colour, font=(font_master_sub, font_master_size_s))
    master_var_select.grid(row=5, column=col, sticky=tk.W+tk.E)
    master_var_tap = tk.Label(frame, text=f'tap. {int(master_tap)}', bg=bg_master_colour, fg=fg_master_colour, font=(font_master_sub, font_master_size_s))
    master_var_tap.grid(row=9, column=col, sticky=tk.W+tk.E)
    
    frame.pack()
    
    update_tk(root, frame, var_tempo, metronomes)
    root.mainloop()

def create_metronomes(metro_func, midi_dispatcher):
    start = True
    while start:
            try:
                num_inst = int(input("How many metronomes (1-7): "))
                if num_inst >= 1 and num_inst <= 8:
                    start = False
                else:
                    print("Wrong Input. Try again")
                    continue
            except:
                print("Wrong Input. Try again")      
    inst_list = list(range(num_inst))
    metronomes = [metro_func(midi_dispatcher, i) for i in inst_list] 
    return metronomes

def create_thread(metronome):
    def inner():
        while True:
            metronome.beat()
    return Thread(target= inner)

if __name__ == "__main__":
    inport = mido.open_input() #check if it has been assigned before
    
    #Creating a dictionary to set MIDI controllers for each metronome on their initialization depending on the metronome inst_number 
    metronomes_controls = {
              'inst_number':[n + 0 for n in range(0,7)], 
              'vol_slide':[n + 0 for n in range(0,7)],
              'tempo_knob': [n + 16 for n in range(0,7)],
              'play_stop': [n + 32 for n in range(0,7)],
              'sync_select': [n + 48 for n in range(0,7)],
              'tap_button': [n + 64 for n in range(0,7)]} 
    #These controls are global. They do not change depending on the metronome inst_number.
    master_controls = {'vol_slide': 7, 'tempo_knob': 23, 'play_stop': 39, 'sync_select': 55, 'tap_button': 71,
                       'tap_metronome': 45, 'sync_selected': 60, 'sync_mode_minus': 61,'sync_mode_plus':62, 'clear_sync_q':46} 

    #global variables to sync metronomes to specific tempo functions
    sync_list = set()
    sync_tempo_list = set()
    sync_selector = 0
    sync_mode_selector = ['MAX','MIN','MIN','AVG','AVG','RAND','RAND'] #['MAX','MIN','AVG','RAND'] 
    sync_mode_selected = 'MAX' #by default
    master_tempo = '_' 
    master_onoff = False
    master_select = False
    master_vol = 100
    master_tap = 0
    
    #Tkinter general variables
    bg_gen_col = 'black'
    fg_gen_col = 'white'
    font_gen = 'TkMenuFont' #font
    font_gen_size = 14 #font size
    font_gen_sub = 'TkHeadingFont'
    font_gen_size_s = 10
    button_gen_colour = '#28393a'
    bg_colour = 'black' #'#3d6466'
    fg_colour= 'white' #text colour
    font_main = 'TkMenuFont' #font
    font_size_m = 14 #font size
    font_sub = 'TkHeadingFont'
    font_size_s = 10
    button_colour = '#28393a'
    bg_master_colour = 'black' #'#3d6466'
    fg_master_colour= 'white' #text colour
    font_master = 'TkMenuFont' #font
    font_master_size = 14 #font size
    font_master_sub = 'TkHeadingFont'
    font_master_size_s = 10
    button_master_colour = '#28393a'
    bg_m_onoff_col = '#28393a'
    bg_m_select_col = '#28393a'
    
    #start Midi dispatcher
    d = MIDIDispatcher(inport)
    d.register('*', master_controls)
    d.start()
    
    #How many metronomes do you need? only one midi controller at the moment
    metronomes = create_metronomes(Metronome, d)
        
    # Create the threads
    threads = [create_thread(metronome) for metronome in metronomes]
    thread_ui = Thread(target=tkinter_ui, args=[metronomes])
    
    # Start metronomes at (almost) the same time
    for t in threads:
        t.start()
    
    #start the ui
    #tkinter_ui(metronomes)
    thread_ui.start()