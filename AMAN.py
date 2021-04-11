""" BlueSky plugin template. The text you put here will be visible
    in BlueSky as the description of your plugin. """
import numpy as np
from math import cos, sin, acos, radians, degrees, atan2, pi, sqrt
import copy
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, sim  #, settings, navdb, sim, scr, tools
#import bluesky.traffic.performance.openap.FlightPhase as FP

Airport_set = 'EHAM'
IAF_set = 'ARTIP'
IAF_other = ["SUGOL","RIVER"]
R = 6371 #earth radius in km
t_update = 10
TBS_min = 2.0 #minimum time separation between aircraft. Can later be changed to RECAT-EU values but is set at 160 seconds for now.
### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = Example()

    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'AMAN',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config


### Entities in BlueSky are objects that are created only once (called singleton)
### which implement some traffic or other simulation functionality.
### To define an entity that ADDS functionality to BlueSky, create a class that
### inherits from bluesky.core.Entity.
### To replace existing functionality in BlueSky, inherit from the class that
### provides the original implementation (see for example the asas/eby plugin).
class Example(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()
        with self.settrafarrays():
            self.AMAN_active = np.array([])
            self.AMAN_IAFpos = np.array([])
            self.AMAN_IAFinRoute = np.array([])
            self.AMAN_actwp = np.array([])
            self.AMAN_distance = np.array([])
            self.AMAN_EAT = np.array([])
            self.AMAN_ddist = np.array([])
            self.AMAN_order = []
            self.AMAN_order_dist = np.array([])
            self.AMAN_accuracy = {}
            self.AMAN_passed = np.array([])
            self.total_order = []
            self.AMAN_order_ex = []
            self.AMAN_order_EAT = np.array([])
            self.AMAN_order_EAT_1 = np.array([])
            self.AMAN_colored = np.array([])
            self.alert = np.array([])

        
    def create(self, n=1):
        ''' This function gets called automatically when new aircraft are created. '''
        # Don't forget to call the base class create when you reimplement this function!
        super().create(n)
        for i in range(traf.ntraf):
                self.AMAN_accuracy[traf.id[i]] = []
                
    @stack.command
    def color_active(self,acid):
        text = acid + " color lime"
        stack.stack(text)

    @stack.command
    def color_inactive(self,acid):
        text = acid + " color blue"
        stack.stack(text)
    
    @stack.command
    def color_unknown(self,acid):
        text = acid + " color yellow"
        stack.stack(text)
        
    @stack.command
    def color_alert(self,acid):
        text = acid + " color red"
        stack.stack(text)

    
    #CORE AMAN simulation
    @core.timed_function(name='example', dt=t_update)
    def sort(self):
        ''' Periodic update function to filter aircraft that are used by the AMAN. '''
        self.AMAN_copy = copy.deepcopy(self.AMAN_active)
    
                
        for idx in range(traf.ntraf):
            route_class = traf.ap.route[idx]
            route = route_class.wpname
            
            #Check if there is an IAF set in the flightplan
            IAF_count = 0
            occurence = 0
            for wpt in route:
                if wpt.strip().upper() == IAF_set:
                    self.AMAN_IAFpos[idx] = IAF_count
                    occurence = 1
                    break
                elif wpt.strip().upper() in IAF_other:
                    occurence = 2
                    break
                IAF_count += 1
            self.AMAN_IAFinRoute[idx] = occurence
            
            #Check which waypoint we currently fly to and if it is before or after the IAF
            actwp_count = 0
            while actwp_count < len(route):
                if route_class.wplat[actwp_count] == traf.actwp.lat[idx]:
                    if route_class.wplon[actwp_count] == traf.actwp.lon[idx]:
                        break
                actwp_count += 1
            self.AMAN_actwp[idx] = actwp_count
            wp_to_go = IAF_count-actwp_count
            if wp_to_go < 0:
                self.AMAN_passed[idx] = 1
            else:
                self.AMAN_passed[idx] = 0



        #Color aircraft that are not relevant but controlled (blue) or aircraft that need guidance(red). 
        #Also activate aircraft for the AMAN (will be colored later)
        for idx in range(traf.ntraf):
            dest = str(traf.ap.dest[idx]).strip().upper()
            if dest == Airport_set:
                if self.AMAN_IAFinRoute[idx] == 1:
                    if self.AMAN_passed[idx] == 0:                   
                        self.AMAN_active[idx] = self.AMAN_IAFpos[idx]+1
                elif self.AMAN_IAFinRoute[idx] == 2:
                    stack.stack("color_inactive %s" %(traf.id[idx]))
                else:
                    stack.stack("color_unknown %s" %(traf.id[idx]))                  
            else:
                self.AMAN_active[idx] = 0
                stack.stack("color_inactive %s" %(traf.id[idx]))
                
            
        #trajectory calculations to calculate EAT 
        for idx in range(traf.ntraf):
            if self.AMAN_active[idx] == 0:  #check whether or not this flight needs sequencing
                continue

            route_class = traf.ap.route[idx]
            wpt_count = int(self.AMAN_actwp[idx])
            distance = 0
            lat_is = radians(traf.lat[idx])
            lon_is = radians(traf.lon[idx])
            spd = traf.cas[idx]
            alt = traf.alt[idx]
            EAT = 0
            while wpt_count <= (self.AMAN_active[idx])-1:
                alt_to = route_class.wpalt[wpt_count]
                if alt_to < 3048:
                    alt_to = 3048
                lat_to = radians(route_class.wplat[wpt_count])
                lon_to = radians(route_class.wplon[wpt_count])
                dis_part = R*(acos(cos(lat_is)*cos(lat_to)*cos(lon_to-lon_is)+sin(lat_is)*sin(lat_to)))
                AoD_part = (alt-alt_to)/dis_part
                dis_level = 0
                if AoD_part < 50: #general angle of descend. Can be extended with aircraft specific angles
                    dis_level = (alt-alt_to)/50
            


                #Determine average wind along the path: resolution is set to 10 km:
                wind_res = 10 #resolution of the wind path
                wind_samples = max(int(dis_part/wind_res),1)
                if wind_samples > 0:
                    dstep = 1/wind_samples
                    step_1 = 1
                    step_0 = 0
                alt_step_1 = 1
                alt_step_0 = 0
                wn = 0 
                we = 0
                wind_dist = dis_part
                for i in range(wind_samples):
                    wind_lat = (step_0*degrees(lat_to))+(step_1*degrees(lat_is))
                    wind_lon = (step_0*degrees(lon_to))+(step_1*degrees(lon_is))
                    #when flying level, altitude over segment does not decrease
                    if wind_dist >= dis_level: 
                        wind_alt = alt
                        alt_samples = wind_samples - i
                        alt_dstep = 1/alt_samples 
                    #expected descend start changing altitude 
                    else: 
                        wind_alt = ((alt_step_1*alt)+(alt_step_0*alt_to))
                        alt_step_1 -= alt_dstep
                        alt_step_0 += alt_dstep
                    step_1 -= dstep
                    step_0 += dstep
                    wn_step, we_step = traf.wind.getdata(wind_lat,wind_lon,wind_alt) #get wind data for current segment
                    wn += wn_step
                    we += we_step
                    wind_dist -= dis_part/wind_samples
                wn = wn/wind_samples #average wind out over path
                we = we/wind_samples #average wind out over path

                
                #calculate bearing of current leg (estimated to work for legs no longer than 100nm)
                bearing = atan2((sin(lon_to-lon_is)*cos(lat_to)),(cos(lat_is)*(sin(lat_to)-sin(lat_is))*cos(lat_to)*cos(lon_to-lon_is)))
                if bearing < 0:
                    bearing += 2*pi
                #get aircraft directional speed over that leg
                ve = sin(bearing)*spd
                vn = cos(bearing)*spd
                spd_wind = sqrt(((vn+wn)**2)+((ve+we)**2)) #correct speed for the wind over leg
                EAT_part = (dis_part/(spd_wind/1000))/60 #estimate EAT for next waypoint
                distance = distance + dis_part #add distances
                EAT = EAT + EAT_part #add EATs to get final arrival times
                spd_new = route_class.wpspd[wpt_count]
                if spd_new <= 0: #When no next leg speed is present it is -999.0. In that case we assume speed stays the same.
                    spd = spd
                else:
                    spd = spd_new
                alt = alt_to
                lat_is = lat_to
                lon_is = lon_to
                wpt_count += 1
                
            
            #update distances and add accuracies to model
            self.AMAN_distance[idx] = distance 
            self.AMAN_EAT[idx]= EAT
            accuracy_list = self.AMAN_accuracy[traf.id[idx]]
            constant_EAT = round((EAT + (sim.simt/60)),2)
            accuracy_list.append(constant_EAT)
            

        
        #Create AMAN order and color active aircraft                
        sort_index = sorted(range(len(self.AMAN_EAT)), key=self.AMAN_EAT.__getitem__)
        count = 0
        for i in sort_index:
            identity = str(traf.id[i])
            if self.AMAN_active[i]>0 and self.AMAN_passed[i] == 0:
                self.AMAN_order[count] = identity
                self.AMAN_order_dist[count] = self.AMAN_distance[i]
                self.AMAN_order_EAT[count] = float(self.AMAN_EAT[i])
                if self.AMAN_colored[i] <1:
                    stack.stack("color_active %s" %identity)
                    self.AMAN_colored[i] = 1
            
            #when aircraft passes the IAF it should be moved out of the AMAN
            elif self.AMAN_passed[i] > 0:
                self.AMAN_order[count] = identity
                self.AMAN_order_dist[count] = self.AMAN_distance[i]
                self.AMAN_order_EAT[count] = float(self.AMAN_EAT[i])
                if self.AMAN_colored[i] <2:
                    stack.stack("color_inactive %s" %identity)
                    self.AMAN_colored[i] = 2
                self.AMAN_order_dist[count] = 10000000
                self.AMAN_order_EAT[count] = 0
                self.AMAN_order[count] = ""
            count += 1
            
        
        #remove blank entries from previously active aircraft. Not the nicest way to program but works
        AMAN_order = ":"
        count = 0
        for i in self.AMAN_order:
            if i != "":
                AMAN_order += str(i)+ ", "
                self.total_order[count] = (str(i))
                count += 1
        stack.stack('ECHO predicted order: at t = %s %s' %(sim.simt,AMAN_order[:-2]))
        
        
        #give proximity warnings for aircraft that arrive at the IAF without seperation
        AMAN_order_EAT = []
        first = 0
        for time in self.AMAN_order_EAT:
            if time == 0:
                continue
            elif first == 0:
                self.AMAN_order_EAT_1[first] = 0
                AMAN_order_EAT.append(0)
            else:
                self.AMAN_order_EAT_1[first] = time
                AMAN_order_EAT.append(time)
            first += 1
          
        for idx in range(1,(len(AMAN_order_EAT))):
            d_time = abs(AMAN_order_EAT[idx]-AMAN_order_EAT[(idx-1)]) #distance between aircraft in front
            if d_time < TBS_min:
                stack.stack('ECHO proximity warning: %s %s' %(self.total_order[idx-1], self.total_order[idx]))
                if (self.alert[idx] % 2) == 0:
                    stack.stack("color_alert %s" %self.total_order[idx])
                    self.alert[idx] = self.alert[idx] + 1
            elif (self.alert[idx] % 2) != 0:
                stack.stack("color_active %s" %self.total_order[idx])
                self.alert[idx] = self.alert[idx] + 1
    
        self.AMAN_active = self.AMAN_copy     
        

    