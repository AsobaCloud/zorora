---
title: "Models Used to Assess the Performance of Photovolt"
orthodoxy: "SME reference (converted from PDF)"
technologies: [solar]
tags: [pdf, sme reference, pv, solar]
weight: 1.0
source_pdf: "Models_Used_to_Assess_the_Performance_of_Photovolt.pdf"
---

<!-- Extracted text; edit frontmatter and body as needed. -->

SANDIA REPORT 
SAND2009-8258 
Unlimited Release 
Printed December 2009 
 
 
 
 
Models Used to Assess the 
Performance of Photovoltaic 
Systems 
 
 
Geoffrey T. Klise and Joshua S. Stein 
 
 
 
Prepared by  
Sandia National Laboratories  
Albuquerque, New Mexico  87185 and Livermore, California  94550 
 
Sandia is a multiprogram laboratory operated by Sandia Corporation,  
a Lockheed Martin Company, for the United States Department of Energy’s  
National Nuclear Security Administration under Contract DE -AC04-94AL85000.  
 
Approved for public release; further dissemination unlimited.  
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 ii 
 
 
 
 
Issued by Sandia National Laboratories, operated for the United States Department of 
Energy by Sandia Corporation. 
 
NOTICE:  This report was prepared as an account of work sponsored by an agency of 
the United States Government.  Neither the United States Government, nor any agency 
thereof, nor any of their employees, nor any of their contractors, subcontractors, or their 
employees, make any warranty, express or implied, or assume any legal liability or 
responsibility for the accuracy, completeness, or usefulness of any information, 
apparatus, product, or process disclosed, or represent that its use would not infringe 
privately owned rights. Reference herein to any specific commercial product, process, or 
service by trade name, trademark, manufacturer, or otherwise, does not necessarily 
constitute or imply its endorsement, recommendation, or favoring by the United States 
Government, any agency thereof, or any of their contractors or subcontractors.  The 
views and opinions expressed herein do not necessarily state or reflect those of the United 
States Government, any agency thereof, or any of their contractors. 
 
Printed in the United States of America. This report has been reproduced directly from 
the best available copy. 
 
Available to DOE and DOE contractors from 
 U.S. Department of Energy 
 Office of Scientific and Technical Information 
 P.O. Box 62 
 Oak Ridge, TN  37831 
 
 Telephone: (865) 576-8401 
 Facsimile: (865) 576-5728 
 E-Mail: 
reports@adonis.osti.gov 
 Online ordering: http://www.osti.gov/bridge 
 
Available to the public from 
 U.S. Department of Commerce 
 National Technical Information Service 
 5285 Port Royal Rd. 
 Springfield, VA  22161 
 
 Telephone: (800) 553-6847 
 Facsimile: (703) 605-6900 
 E-Mail: 
orders@ntis.fedworld.gov 
 Online order: http://www.ntis.gov/help/ordermethods.asp?loc=7-4-
0#online 
 
 
 
 
 

 iii 
SAND2009-8258 
Unlimited Release 
Printed December 2009 
 
 
Models Used to Assess the Performance of Photovoltaic 
Systems 
 
 
Geoffrey T. Klise 
Earth Systems Department 
Sandia National Laboratories 
P.O. Box 5800 
Albuquerque, NM 87185 
 
Joshua S. Stein 
Photovoltaics and Grid Integration Department 
Sandia National Laboratories 
P.O. Box 5800 
Albuquerque, NM 87185 
 
 
Abstract 
 
This report documents the various photovoltaic (PV) performance models and software 
developed and utilized by researchers at Sandia National Laboratories (S NL) in support 
of the Photovoltaics and Grid Integration Department. In addition to PV performance 
models, hybrid system and battery storage models are discussed. A hybrid system using 
other distributed sources and energy storage can help reduce the variability inherent in 
PV generation, and due to the complexit y of combining multiple generation sources and 
system loads, these models are invaluable for system design and optimization. Energy 
storage plays an important role in reducing PV intermittency and battery storage models 
are used to understand the best conf igurations and technologies to store PV generated 
electricity. Other researcher’s models used by S NL are discussed including some widely 
known models that incorporate algorithms developed at S NL. There are other models 
included in the discussion that are not used by or were not adopted from S NL research 
but may provide some benefit to researchers working on PV array performance, hybrid 
system models and energy storage. The paper is organized into three sections to describe 
the different software models as applied to photovoltaic performance, hybrid systems, 
and battery storage. For each model, there is a description which includes where to find 
the model, whether it is currently maintained and any references that may be available. 
Modeling improvements under way at S NL include quantifying the uncertainty of 
individual system components, the overall uncertainty in modeled vs. measured results 
and modeling large PV systems. S NL is also conducting research into the overall 
reliability of PV systems. 
 iv 
Acknowledgments 
 
The authors would like to thank Charles Hanley, Christopher Cameron, Dan Riley, 
Abraham Ellis, Richard Chapman, David Trujillo, Dave Menicucci, David King, Tom 
Hund, John Boyes, Rudy Jungst, Terry Aselage, David Ingersoll and William Beckman 
for provi ding information on models used to simulate performance in PV, hybrid and 
battery storage systems.  
Sandia is a multiprogram laboratory operated by Sandia Corporation, a Lockheed Martin 
Company for the United States Department of Energy’s National Nuclear Security 
Administration under contract DE-AC04-94AL85000. 
 v 
Contents 
Acronyms and Abbreviations ...................................................................................................... 1 
1. Introduction ........................................................................................................................... 3 
2. PV Performance Models....................................................................................................... 4 
2.1 Sandia National Laboratories PV Modeling Timeline..................................................... 5 
2.2 PV Models Developed and Used by Sandia National Laboratories ................................ 6 
2.2.1 PVSS .................................................................................................................... 6 
2.2.2 SOLCEL .............................................................................................................. 7 
2.2.3 Evans and Facinelli Model................................................................................... 8 
2.2.4 PVForm ................................................................................................................ 9 
2.2.5 PVSIM ............................................................................................................... 11 
2.2.6 Sandia Photovoltaic Array Performance Model ................................................ 11 
2.2.7 Sandia Inverter Performance Model .................................................................. 13 
2.2.8 PVDesignPro...................................................................................................... 14 
2.2.9 Solar Advisor Model .......................................................................................... 14 
2.3 Other PV Performance Models ...................................................................................... 17 
2.3.1 5-Parameter Array Performance Model ............................................................. 17 
2.3.2 PVWatts ............................................................................................................. 18 
2.3.3 PVSYST ............................................................................................................. 19 
2.3.4 PV F-Chart ......................................................................................................... 20 
2.3.5 RETScreen Photovoltaic Project Model ............................................................ 21 
2.3.6 PVSol ................................................................................................................. 22 
2.3.7 Polysun ............................................................................................................... 23 
2.3.8 INSEL ................................................................................................................ 23 
2.3.9 SolarPro.............................................................................................................. 24 
2.4 Simplified PV Performance Models .............................................................................. 25 
2.4.1 Clean Power Estimator ...................................................................................... 25 
2.4.2 PVOptimize........................................................................................................ 26 
2.4.3 OnGrid ............................................................................................................... 26 
2.4.4 CPF Tools .......................................................................................................... 27 
2.4.5 Solar Estimate .................................................................................................... 27 
3. Hybrid System Models ....................................................................................................... 28 
3.1 Hybrid System Models Developed and Used by Sandia National Laboratories ........... 29 
3.1.1 SOLSTOR .......................................................................................................... 29 
3.1.2 HybSim .............................................................................................................. 30 
3.1.3 Hysim ................................................................................................................. 30 
3.2 Other Hybrid System Models ........................................................................................ 31 
3.2.1 HOMER ............................................................................................................. 31 
3.2.2 Hybrid2 .............................................................................................................. 32 
3.2.3 UW-Hybrid (TRNSYS) ..................................................................................... 33 
3.2.4 RETScreen ......................................................................................................... 33 
3.2.5 PVToolbox ......................................................................................................... 34 
3.2.6 RAPSIM ............................................................................................................. 35 
 vi 
3.2.7 SOMES .............................................................................................................. 35 
3.2.8 IPSYS ................................................................................................................. 36 
3.2.9 HySys ................................................................................................................. 37 
3.2.10 Dymola/Modelica .............................................................................................. 37 
4. Battery Performance Models ............................................................................................. 38 
4.1 Battery Performance Models Developed and Used by Sandia National 
Laboratories ................................................................................................................... 39 
4.1.1 SIZEPV .............................................................................................................. 39 
4.1.2 Artificial Neural Network Technique ................................................................ 39 
4.2 Other Battery Performance Models ............................................................................... 40 
4.2.1 KiBaM................................................................................................................ 40 
4.2.2 FhG/Riso ............................................................................................................ 41 
4.2.3 CIEMAT ............................................................................................................ 42 
4.2.4 CEDRL .............................................................................................................. 43 
5. PV Modeling Effort Improvements Underway at Sandia National Laboratories ........ 43 
5.1 PV Model Validation ..................................................................................................... 44 
5.2 Model Uncertainty and Sensitivity ................................................................................ 44 
5.3 Modeling Large PV Plants ............................................................................................. 45 
6. Assertion of Copyright ....................................................................................................... 45 
References .................................................................................................................................... 46 
APPENDIX A .............................................................................................................................. 53 
 
Figures 
Figure 1.  Photovoltaic Balance-of-Systems (Credit: Florida Solar Energy Center)   .......... 5
Figure 2.  Hierarchy of PV and hybrid system models that use PVForm   ......................... 10
Figure 3.  Illustration of a Hybrid Electric Power System   ................................................ 29
 
Tables 
Table 1.   Algorithm Options in SAM for Solar Radiation, Array and Inverter 
Performance   ...................................................................................................................... 16
 
 1 
Acronyms and Abbreviations 
 
Ah  Amp-hour 
AIAA  American Institute of Aeronautics and Astronautics 
ANN  artificial neural network 
aSi  amorphous silicon 
BIPV  building integrated photovoltaic 
BOS   balance-of-system(s) 
CdTe  cadmium telluride 
CEC  California Energy Commission 
CIEMAT Centro de Investigaciones Energeticas, Medioambientales y 
Technologicas 
CiS copper-indium (di)selenide or copper-indium gallium (di)selenide 
technologies 
CPE  Clean Power Estimator 
CPV  concentrating photovoltaic (crystalline unless stated otherwise) 
cSi  crystalline silicon 
CSI  California Solar Initiative 
CSV  comma separated value 
CVA  canonical variate analysis 
CWEC  Canadian Weather for Energy Calculations 
DOE  Department of Energy 
EPRI  Electric Power Research Institute 
EPW  EnergyPlus Weather 
EU  European Union 
EV  electric vehicle 
HDKR  Hay, Davies, Klucher, Reindl 
HIT  hetero-junction intrinsic thin layer 
IEA  International Energy Agency 
IMBY  In My Backyard 
Imp  current at maximum power point 
IMS  internet map server 
INSEL  Integrated Simulation Environment Language 
IPAL  Intellectual Property Available for Licensing 
IRR  internal rate of return 
Isc  short-circuit current 
ISE  Institute for Solar Energy 
ISES  International Solar Energy Society 
IWEC  International Weather for Energy Calculations 
LCOE   levelized cost of energy 
mj  multi-junction 
µc  micro-crystalline 
MPPT  maximum power point tracking 
MSEC   Maui Solar Energy Software Corporation 
MUERI Murdoch University Energy Research Institute 
 2 
NASA  National Aeronautics and Space Administration 
NASA SSE NASA Surface Meteorological and Solar Energy Program 
NIST  National Institute for Standards and Technology 
NPV  net present value 
NREL  National Renewable Energy Laboratory 
NRSDB National Solar Radiation Data Base 
NSHP  New Solar Homes Partnership 
O&M  operations and maintenance 
POA  plane of array 
PPA   power purchase agreement 
PV  photovoltaic 
PVSC  Photovoltaic Specialists Conference 
PVSS  Photovoltaic System Simulation Program 
RAPSIM Remote Area Power Simulator 
RER  Renewable Energy Research 
RERL  Renewable Energy Research Laboratory 
RISE  Research Institute for Sustainable Energy 
RPS   renewable portfolio standard 
SAM   Solar Advisor Model 
SEL  Solar Energy Laboratory 
SERI  Solar Energy Research Institute 
SOC  state-of-charge 
SOMES  Simulation and Optimization Model for Renewable Energy Systems 
STC  standard test conditions 
SWERA Solar and Wind Energy Resource Assessment 
TMY  Typical Meteorological Year 
USHCN  US Historical Climatology Network 
Voc  open-circuit voltage 
Vmp  voltage at maximum power point 
WRDC World Radiation Data Center 
 
 3 
1. Introduction 
Sandia National Laboratories ( SNL) plays a leading role in the development and 
application of photovoltaic (PV) technology used for generating electricity. These efforts 
include research, development and performance modeling of crystalline silicon, thin-film, 
concentrating PV, and inverter technologies and working to transfer this knowledge to 
end-users in a way that will increase the utilization of PV systems for generating 
electricity. 
 
In order to support this work, S NL has been instrumental in developing computer 
modeling tools that can  be used to design, monitor and predict PV and energy storage 
system performance for specific research needs. Some of these tools have been 
incorporated into third- party software that includes both free and commercial 
applications, while others have been developed and applied exclusively by researchers at 
SNL.  
 
The photovoltaic industry is poised to undergo a period of rapid growth due to many 
factors, including but not limited to the following: A growing desire by people to reduce 
their carbon emissions, establishment of state renewable portfolio standards (RPS), use of 
third-party power purchase agreements (PPAs), new federal tax incentives for 
manufacturing and installation, new PV cell, inverter and storage technologies, and a 
decrease in the cost of PV system components. 
 
As more PV systems are installed, there will be an increase in demand for software that 
can be used for design, analysis and troubleshooting. One example outlining the 
importance of PV performance monitoring is that new regulatory devices are being put 
into place that make the amount of tax credit returned from an installation conditional on 
the amount of electricity generated  by a PV system. An incomplete assessment of a PV 
system’s capabilities can underestimate system payback and affect possible financing. 
When new PV technologies are deployed, predicted and actual performance data will be 
included in databases, and other as sumptions may require significant changes to the 
existing empirical and analytical techniques that are currently used. Folding in the PV 
performance algorithms into hybrid simulation models for micro -grid applications is 
important as distributed generation  and renewable energy use becomes more established 
in the U.S. The use of batteries for both small and large -scale energy storage and power 
conditioning will also be important as PV grid penetration increases. 
 
A comprehensive understanding of available models, capabilities, tradeoffs and 
shortcomings will be necessary to keep up with changes in technology and differing 
needs by end-users both now and in the future. This new phase of PV deployment in the 
U.S. will be successful if the photovoltaic, hybrid s imulation and battery modeling tools 
can address these new challenges. 
 
The paper is divided into three main sections: 1) PV performance models 2) hybrid 
system performance models and 3) battery storage models. There is some overlap 
 4 
between the sections du e to the fact that hybrid systems incorporate both individual PV 
performance and battery storage algorithms. It is likely that there are some models used 
by academia or industry that are not widely advertised, and therefore are not included in 
this discussion. In addition, this paper does not repres ent an exhaustive search of models 
used to simulate other energy storage technologies  such as flywheels, capacitors, 
compressed air, or pumped hydro. References are provided within each section and at the 
end of the paper. Any available hyperlinks are included and represent the location of 
reports publically available at the time this paper was written in late 2009. A summary 
table is presented in Appendix A to differentiate PV and hybrid model types in terms of 
system components or entire systems models. Finally, we present a discussion of current 
work being done at S NL in the areas of PV performance model  enhancements and  
improvements. 
2. PV Performance Models 
Photovoltaic performance models are used to estimate the  power output of a photovoltaic 
system, which typically includes PV panels, inverters, charge controllers and other 
“balance of system” (BOS) components (Figure 1). These models create a generation 
profile based on a specific geographic location which helps determine how much solar 
irradiance is available for harvesting. The meteorological inputs for any given location 
vary by latitude, season and changing weather patterns; being able to accurately 
determine the generation profile due to these changing vari ables results in better 
matching of system load with expected generation. Some models make general 
assumptions about system components and ratings while other more complex models 
take into account manufacturer parameters, derived parameters and empirically  derived 
data. These models can also be used to evaluate system performance over time by 
providing a baseline to compare with if performance suddenly decreases and 
troubleshooting is necessary.  
Financial considerations are also important when considering PV; some models are 
considered “system” models due to the inclusion of capital and operating costs as well as 
expected benefits in terms of payback period, avoided costs, internal rate of return , 
levelized cost -of-energy (LCOE), cash flow and depreciable basis, just to name a few. 
System derate factors are also important as equipment degrades over time resulting in a 
power output decrease. 
This section begins with models developed and used by researchers at Sandia National 
Laboratories presented in chronological order, then discusses models other researchers 
utilize when evaluating PV system performance, and ends with a discussion of simplified 
PV performance models. Only models with English language versions are included in 
this assessment. A table of the P V models and important characteristics is presented in 
Appendix A. 
  
 5 
 
 
 
 
 
 
 
 
Figure 1.  Photovoltaic Balance-of-Systems (Credit: Florida Solar Energy Center) 
 
2.1 Sandia National Laboratories PV Modeling Timeline 
An annotated history of the many early models developed at S NL used to predict PV 
performance is presented by King et al. (2004). There are however many other algorithms 
developed at S NL that go back to the 1970’s and are summarized below. A detailed 
description of these model s is presented in the following subsections in chronological 
order. 
The earliest efforts at SNL for modeling PV cells, arrays and system cost can be found in 
the PVSS program by Goldstein and Case (1977), the SOLCEL systems analysis program 
by Linn (1977) and Hoover (1979), and followed by Evans et al. (1978; 1980), and Evans 
(1981). Around the same time, SOLSTOR (Aronson et al., 1979; Aronson et al., 1982) 
was created as a hybrid system model that could look at wind and energy storage in 
addition to PV. The PV performance algorithms in SOLSTOR were expanded from work 
done in SOLCEL. The model PVForm (Menicucci 1985, 1986; Menicucci and 
Fernandez, 1988) was built to improve and simplify the codes developed in SOLCEL and 
provide a systems modeling approach. S ome of the array performance algorithms 
developed in PVForm have been widely incorporated into a number software programs 
that will be discussed in more detail later in this paper. 
These models were followed in 1996 with an effort to better characterize and describe 
cell and module electrical performance with a model called PVSIM (King et al., 1996) 
which used empirically derived module parameters to better define cell or module 
performance for a wide range of temperatures. PVMOD was developed through a 
separate effort in 1998 from module testing that started in 1991. The purpose of this 
testing was to empirically derive performance estimates from PV modules under a variety 
of operating conditions. PVMOD uses a simplified solar radiation algorithm and is sti ll 
used in 2009 for analysis. 
The Sandia PV Array Performance Model resulted from further refinements of the work 
initially done in PVMOD. S NL worked with the Maui Solar Energy Software 
Corporation (MSESC) in 1998 to include its array and inverter performa nce algorithms 
into the commercially available PVDesignPro software (MSESC, 2004), and worked on 
validating the model as well as providing supporting documentation. The S NL model is 

 6 
also included in the systems level Solar Advisor Model (SAM) maintained by  the 
National Renewable Energy Laboratory (NREL). 
Around the same time PVSIM and the Sandia PV Array Performance Model were in 
development, two hybrid system models were being designed. The first model Hys im, by 
Chapman (1996) was designed for remote stand -alone military facilities using a PV -
diesel-battery configuration. The  second model HybS im, by Kendrick et al. (2003) 
models remote hybrid systems and adds wind as an additional genera tion source. Both 
HybSim and Hysim represent independent modeling efforts. 
2.2 PV Models Developed and Used by Sandia National 
Laboratories 
2.2.1 PVSS 
Description 
The Photovoltaic System Simulation Program (PVSS) developed by S NL is a simple 
component model built in FORTRAN to simulate PV system performance by allowing 
the user to choose a variety of different system configurations for both on and off -grid 
PV systems.  
A plane of array (POA) radiation model was not used in this model. Array performance is 
based on a one -diode equivalent circuit equation for determining the current -voltage (I-
V) curve. Temperature effects on irradiance are based on equation that is a function of the 
band-gap, a silicon specific constant, Boltzmann’s constant and the cell temperature. 
(Lewis and Kirkpatrick, 1970). Based on the year the model was developed, Flat plate 
crystalline silicon (cSi) is probably the only modeled PV technology. The user manual 
does not mention the use of any common weather databases for weather or insolation, 
though it appears these values can be altered easily by the user to incorporate site-specific 
information. This model does not perform any economic or financing analysis. 
For lead-acid battery storage, state-of-charge and power delivered or received is tracked.  
Availability and Maintenance 
PVSS was developed in the 1976- 1977 timeframe based on the references described 
below. The program is no longer used, updated or supported by SNL. 
References 
• Goldstein, L. H, and G. R. Case, 1977, PVSS – A Photovoltaic System Simulation 
Program Users Manual, SAND77-0814. Sandia National Laboratories, 
Albuquerque, NM, June 1977. 
• Goldstein, L. H., and G. R. Case, 1978, PVSS – A Photovoltaic System Simulation 
Program, Solar Energy, Vol. 23, No. 1, pp.37-43. 
 7 
• Lewis, C. A., and J. P. Kirkpatrick, 1970, Solar Cell Characteristics at High 
Solar Intensities and Temperatures, 8th IEEE PVSC, Seattle, WA, August 4-6, 
1970. 
2.2.2 SOLCEL 
Description 
SOLCEL is a system -level model used for both grid -tied and off -grid (battery storage) 
PV systems. It is implemented in FORTRAN and can run simula tions down to an hourly 
time-step.  
A simple equivalent circuit model as described in PVSS ( Section 2.2.1) is used to model 
array performance. Temperature effects on array performance are determined using a 
temperature-corrected efficiency model based on P VSS and modified based on different 
passive and active cooling configurations. The program can model both flat -plate and 
concentrating PV (CPV) incorporated onto trackers or fixed arrays.  Weather and solar 
insolation data for the model is obtained using the SOLMET Typical Meteorological 
Year (TMY) database.
1
SOLCEL is set up to look at different scenarios to determine the best system design for a 
desired range of costs including, but not limited to PV energy cost, total system cost, life -
cycle cost, and rat e of return. The two economic -evaluation techniques the program 
implements are the life -cycle costing methodology and the Department of Energy 
(DOE)/Electric Power Research Institute (EPRI) required revenue methodology. 
SOLCEL can also find the optimal configuration with the lowest life -cycle cost (Hoover, 
1980). 
 
Availability and Maintenance 
SOLCEL consisted of three versions. SOLCEL -I was developed around 1976- 1977 
timeframe, followed by an updated version, SOLCEL -II in 1979- 1980. SOLCEL -III is 
mentioned by SERI (1985) in an early computer models directory, and was available for 
use around 1985 though no formal documentation is available. SOLCEL is no longer 
being used, updated or supported by S NL. Some equations used in the models can be 
found in the following references. 
References 
• Linn, J. K., 1977, Photovoltaic System Analysis Program – SOLCEL, SAND77-
1268. Sandia National Laboratories, Albuquerque, NM, August 1977. 
• Evans, D. L., W. A. Facinelli and R. T. Otterbein, 1978, Combined 
Photovoltaic/Thermal System Studies, SAND78-7031. Sandia National 
Laboratories, Albuquerque, NM, August 1978. 
                                                 
1 The 26 SOLMET sites gathered hourly measurements from 1952-1975 and was replaced by the National 
Solar Radiation Data Base (NSRDB) measurements for the time period of 1961 -1990. 
 8 
• Hoover, E. R., 1980, SOLCEL-II An Improved Photovoltaic System Analysis 
Program, SAND79-1785. Sandia National Laboratories, Albuquerque, NM, 
February 1980. 
• Solar Energy Research Institute (SERI), 1985, Solar Energy Computer Models 
Directory, SERI/SP-271-2589. Solar Energy Research Institute, Golden, CO, 
August 1985. 
2.2.3 Evans and Facinelli Model 
Description 
A photovoltaic performance model for PV  systems was developed by Arizona State 
University under contract with Sandia National Laboratories. In the model, system 
performance is analyzed when using a battery or converted energy from the array for 
maximum power point tracking (MPPT). The assumption in this model is that the PV 
arrays only generate power at the maximum power point on the I -V curve (Evans et al., 
1981).  
The model runs on a monthly time-step and is implemented in the TRNSYS environment 
(see Section 3.2.3 for more discussion on TRNSYS). For POA irradiance, a tilt correction 
factor is used and the arrays are either tracking or moved monthly to optimize energy 
production. For array performance, a power temperature coefficient model considers the 
efficiency, temperature and tilt correctio n factor. Technologies modeled include cSi and 
CPV with weather and insolation data taken from the SOLMET TMY database.  
Availability and Maintenance 
This model was developed in the late 1970s and early 1980s and is no longer used, 
updated or supported by S NL. Many of the equations used to develop the model are 
described in the references below. 
References 
• Evans, D. L., W. A. Facinelli and R. T. Otterbein, 1978, Combined 
Photovoltaic/Thermal System Studies, SAND78-7031. Sandia National 
Laboratories, Albuquerque, NM, August 1978. 
• Evans, D. L., W. A. Facinelli, and L. P. Koehler, 1980, Simulation and Simplified 
Design Studies of Photovoltaic Systems, SAND80-7013. Sandia National 
Laboratories, Albuquerque, NM, September 1980. 
• Evans, D. L., W. A. Facinelli, and L. P. Koehler, 1981, Simplified Design Guide 
for Estimating Photovoltaic Flat Array and System Performance, SAND80-7185. 
Sandia National Laboratories, Albuquerque, NM, March 1981. 
• Evans, D. L., 1981, Simplified Method for Prediction Photovoltaic Array Output, 
Solar Energy, Vol. 27, No. 6, pp. 555-560. 
 9 
2.2.4 PVForm 
Description 
PVForm by Menicucci (1985) was one of the first “system” models for PV applications 
that can analyze and compare system performance in one or many locations with the 
benefit of incorporating system costs. The model has the ability to look at both grid- tied 
and stand- alone systems (with battery storage) and can allow a user to model system 
degradation, and the effects of load and component changes.  
PVForm was also built to both simplif y and improve the SOLCEL model (Section 2.2.2) 
by Linn (1977) and Hoover (1979). Some of the major technical improvements as 
compared to earlier models developed by S NL include changing solar insolation 
calculations for flat plate and POA orientations using the newly developed Perez model 
(Perez et al., 1987, 1988), a simpler modified power temperature coefficient model for 
array performance, and inclusion of a thermal m odel for module temperature by Fuentes 
(1987). PVForm appears to only model flat plate cSi. For weather and solar insolation, 
the TMY dataset is utilized. For financial information, PVForm gives users the ability to 
understand important metrics such as LCO E for comparing the cost of other electricity 
generating technologies with PV. 
A validation test of the battery modeling algorithm in PVForm is described by 
Chamberlin (1988) where performance from flooded, gelled and absorbed- electrolyte 
lead-acid batteries was evaluated when coupled with a PV system. 
Availability and Maintenance 
PVForm was created in 1985 as a stand- alone program for PC computers running MS -
DOS. Version 3.3 as described in Menicucci and Fernandez (1988) was the last update to 
PVForm. The program is no longer being used or maintained by S NL, but is available at 
IPAL for licensing 
http://ipal.sandia.gov/Default.php. 
Programs that Use PVForm 
Because of its simplicity, many different programs utilize portions of PVForm, especially 
PVWatts, one of the more widely known and utilized models discussed below in Section 
2.3.2. Figure 2 shows the many PV and hybrid systems models that incorporate the POA 
and array performance algorithms from PVForm. The se models are discussed in more 
detail in subsequent sections. 
 10 
 
Figure 2.  Hierarchy of PV and hybrid system models that use PVForm 
 
References 
• Linn, J. K., 1977, Photovoltaic System Analysis Program – SOLCEL, SAND77-
1268. Sandia National Laboratories, Albuquerque, NM, August 1977. 
• Hoover, E. R., 1980, SOLCEL-II An Improved Photovoltaic System Analysis 
Program, SAND79-1785. Sandia National Laboratories, Albuquerque, NM, 
February 1980. 
• Menicucci, D. F., 1985, PVFORM – A New Approach to Photovoltaic System 
Performance Modeling, 18th IEEE PVSC, Las Vegas, NV, October 21-25, 1985. 
• Menicucci, D. F., 1986, Photovoltaic Array Performance Simulation Models, 
Solar Cells, Vol. 18, pp. 383-392. 
• Fuentes, M. K., 1987, A Simplified Thermal Model for Flat-Plate Photovoltaic 
Arrays, SAND85-0330. Sandia National Laboratories, Albuquerque, NM, May 
1987. 
• Perez, R., R. Stewart, C. Arbogast, R. Seals and D. Menicucci, 1987, A New 
Simplified Version of the Perez Diffuse Irradiance Model for Tilted Surfaces, 
Solar Energy, Vol. 39, pp. 221-231. 
• Perez, R., R. Stewart, R. Seals, T. Guertin, 1988, The Development and 
Verification of the Perez Diffuse Radiation Model, SAND88-7030. Sandia 
National Laboratories, Albuquerque, NM, October 1988. 

 11 
• Menicucci, D. F., and J. P. Fernandez, 1988, User’s Manual for PVFORM: A 
Photovoltaic System Simulation Program for stand-alone and grid-interactive 
applications, SAND85-0376. Sandia National Laboratories, Albuquerque, NM, 
April 1988. 
• Chamberlin, J. L., 1988, Performance Modeling of Lead-Acid batteries in 
Photovoltaic Applications, 20th IEEE PVSC, Las Vegas, NV, September 26-30, 
1988. [SAND88-0594C] 
2.2.5 PVSIM 
Description 
PVSIM was developed at S NL by King et al. (1996) to better understand the electrical 
behavior between each module in an array. Specifically, it was built to take a look at 
module mismatch and shading loss. This analysis is done using a two- diode equivalent 
circuit model with empirically derived parameters from dark I -V measurements at a low 
(25°C) and high (50°C) cell temperatures. The software program allows for users to enter 
their parameters to create cell I -V curves determined through testing. From there, users 
can see how an array would perform at a variety of different operating temperatures. 
Availability and Maintenance 
The basic two -diode equivalent circuit equations in PVSIM are presented in the paper. 
PVSIM is not currently being distributed or used by SNL, although renewed interest from 
the PV industry is leading to efforts to translate the software to a new platform for future 
analysis. 
References 
• King, D. L., J. K. Dudley, and W. E. Boyson, 1996, PVSIM: A Simulation 
Program for Photovoltaic Cells, Modules, and Arrays, 25
th IEEE PVSC, 
Washington, DC, May 13-17, 1996. [SAND95-2673C]  
2.2.6 Sandia Photovoltaic Array Performance Model 
Description 
The Sandia PV Array Performance Model (King et al., 2004) utilizes a database of 
empirically derived PV module parameters developed by testing modules from a variety 
of manufacturers. The data can be used to evaluate the performance of PV systems in 
three ways: 
 
1) Design a PV system to properly match desired generation with lo ad 
information on timescales that vary from one hour to one year; 
2) Calculate the system power rating from module -specific empirically derived 
formulas developed at SNL, and 
 12 
3) Provide long term analysis capabilities that are useful for measuring array 
performance and troubleshooting support.   
Where other algorithms attempt to determine array performance in conditions that are not 
optimal (most of the time), using theoretical and semi- empirical methods, the Sandia PV 
Array Performance Model is a departure from many of the earlier equations used to 
derive power from a PV system as it is based on empirical measurements made for 
modules in conditions other than the manufacturer provided standard test conditions 
(STC).  
This model calculates the Isc, Imp, Vmp, Voc, and two other current values at 
intermediate points. This is accomplished with a curve -fitting process using coefficients 
derived from module testing. Empirical coefficients are also developed to calculate 
parameters that are temperature dependent  (including a module specific thermal model), 
effects of air mass and angle of incidence on the short -circuit current, and type of 
mounting (whether rack mounted or BiPV). This model also allows for the determination 
of an “effective irradiance”, which is the amoun t of irradiance that actually reaches the 
cells after other losses are taken into consideration. 
This model is considered a component model as it only models PV Arrays. Besides cSi, 
the model has been applied to thin films including cadmium telluride (CdTe ) copper -
indium selenide (CiS) and amorphous silicon (aSi), CPV, and multi -junction (mj) CPV. 
Weather and insolation data can come from any source. As implemented in PVDesign 
Pro (Section 2.2.8)  and the Solar Advisor Model (Section 2.2.9), it can use TMY2,  
TMY3 and METEONORM weather and solar insolation data. 
This approach has its limitations in that the modules have to undergo additional testing to 
obtain parameters other than what is provided by the manufacturer. However, validation 
of the model performed  by National Institute for Standards and Technology (NIST) and 
SNL shows the model can predict power output to within 1% of measured power in 
different geographic locations (Fanney et al., 2006). In addition, the model has also been 
applied to Building Int egrated PV (BIPV), and when compared with the 5- parameter 
model described later in Section 2.3.1, the S NL model better predicts measured power 
output (Fanney et al., 2002). The S NL model is also being used extensively by NIST for 
evaluating performance of cSi and tandem -junction aSi BIPV modules (Fanney et al., 
2009).  
Availability and Maintenance 
This software was developed in many stages between 1991 and 2004. All of the 
equations used by the current PV Array Performance Model (and early prototype 
PVMOD) are described in the King et al. (2004) paper and are utilized in both 
PVDesignPro (Section 2.2.8) and the Solar Advisor Model (Section 2.2.9). This is the 
primary model used by researchers at S NL to calculate array performance at the time of 
this publication. As of 2009, testing is being conducted in Tempe, Arizona for new PV 
modules by TUV Rheinland PTL. These results will go into the S NL module database, 
which is accessible within the Solar Advisor Model and PVDesign Pro. 
 13 
References 
• Fanney, A. H., B. P. Dougherty, and M. W. Davis, 2002, Evaluating Building 
Integrated Photovoltaic Performance Models, 29th IEEE Photovoltaic Specialists 
Conference, New Orleans, LA, May 17 and 24 2002. 
• King, D. L., W. E. Boyson and J. A. Kratochvil, 2004, Photovoltaic Array 
Performance Model, SAND2004-3535. Sandia National Laboratories, 
Albuquerque, NM, August, 2004. 
• Maui Solar Energy Software Corporation (MSESC), 2004, PV-DesignPro v6.0 & 
Solar Design Studio, Available at: http://www.mauisolarsoftware.com.  
• Fanney, A. H., M. W. Davis, B. P. Dougherty, D. L. King, W. E. Boyson, and J. 
A. Kratochvil, 2006, Comparison of Photovoltaic Module Performance 
Measurements, J. of Solar Energy Engineering, Vol. 128, No. 2, pp. 152-159. 
• Fanney, A. H., B. P. Dougherty, and M. W. Davis, 2009, Comparison of 
Predicted to Measured Photovoltaic Module Performance, Solar Energy 
Engineering, Vol. 131, No. 2, 10p.  
2.2.7 Sandia Inverter Performance Model 
Description 
The Sandia Inverter Performance Model for grid- tied systems (King et al., 2007) 
characterizes efficiencies in the conversion process from dc- power to ac -power using an 
empirical method (like the Sandia PV Array Performance Model) through the testing of 
operating inverters. Inverter performance is characterized as a function of input power 
and voltage, and coefficients are derived that can be used in the model. The results of the 
testing include an inverter parameter database with equations that can be utilized with the 
Sandia PV Array Performance Model. This model is included in PVDesignPro ( Section 
2.2.8) and the Solar Advisor Model (Section 2.2.9). 
Availability and Maintenance 
The database as compiled by King et  al. (2007) is the original version. The inverters in 
this database were selected as part of a long -term effort to study how performance 
changes through time. Additional parameters from testing by the California Energy 
Commission (CEC) are included in upda tes to the databases used in the Solar Advisor 
Model and available at: 
https://www.nrel.gov/analysis/sam/download.html. This is the 
primary model used by researchers at S NL to calculate inverter  performance at the time 
of this publication.  
References 
• King, D. L., S. Gonzalez, G. M. Galbraith, and W. E. Boyson, 2007, Performance 
Model for Grid-Connected Photovoltaic Inverters, SAND2007-5036. Sandia 
National Laboratories, Albuquerque, NM, September 2007. 
 14 
2.2.8 PVDesignPro 
Description 
PVDesignPro software is a commercially available software model developed by the 
Maui Solar Energy Software Corporation (MSESC) and S NL for photovoltaic systems 
modeling. The software incorporates algorithms from both of S NL’s PV array and 
inverter performance models as well as S NL’s database of PV module and inverter 
parameters. NIST uses a custom version of PVDesignPro for comparing dif ferent PV 
technologies and predicting PV module performance for BIPV applications. Some of 
these tests using PVDesignPro are described above in Section 2.2.6. 
The program uses an hourly time -step for modeling system performance. Two solar 
radiation models are available: the Hay, Davies, Klucher, Reindl (HDKR)  model (Duffie 
and Beckman, 1991) and the Perez et al.  (1987, 1988) model. Array performance is 
modeled using the Sandia PV Array Performance Model. Modeled technologies include 
cSi, thin-film (CdTe, CiS, and aSi), CPV, and mj -CPV. For weather and solar insolation, 
PVDesignPro uses TMY2, EPW (TMY3) and METEONORM data. 
If financial analysis is desired, the software will take system cost inputs to determine cash 
flow, payback period, internal rate of retur n, and utility avoided costs. Battery state -of-
charge can be tracked for systems with battery backup. 
Availability and Maintenance 
PVDesignPro is available at 
http://www.mauisolarsoftware.com in various configurations 
for small systems and large utility systems. It also has the ability to model battery 
storage, off -grid systems, water pumping, and solar water heating.  The software was 
developed in 1998 with the most recent version of the software (v6.0) update d in 2004 at 
the time of this report. The climate and module database were kept up -to-date at the time 
of this report. 
References 
• Maui Solar Energy Software Corporation (MSESC), 2004, PV-DesignPro v6.0 & 
Solar Design Studio, Available at: 
http://www.mauisolarsoftware.com  
2.2.9 Solar Advisor Model 
Description 
The Solar Advisor Model or SAM, as it is commonly referred to, is a stand- alone 
software program created in 2006 by a partnership with the National Renewable Energy 
Laboratory (NREL) and SNL through the DOE Solar Energy Technologies Program. The 
model is being continuously updated and improved and has an active user community 
that can be accessed at: 
http://groups.google.com/group/sam-user-group. The early 
concept name for this program was PVSunVisor and a report by Mehos and Mooney 
(2005) prior to full model release discusses the impetus for creating a comprehensive 
modeling tool.  
 15 
This model is considered a “system” model because it has the ability to model PV system 
performance, and perform financial analysis. A useful feature in SAM is that it provides 
access to many different array performance models described below in Table 1.  
POA radiation models  in SAM include Isotropic Sky (Liu and Jordan, 1963), Hay and 
Davies ( Davies and Hay, 1980), Reindl  (1988) and Perez et al. (1987, 1988) Modeled 
technologies include cSi, thin- film (CdTe, CiS, and aSi), CPV, mj -CPV and hetero -
junction intrinsic thin layer (HIT). SAM can also look at other solar technologies such as 
Dish Stirling, parabolic trough and power tower systems. For array performance, Table 1 
below shows the four different options. SAM uses the Transient Systems Simulation 
(TRNSYS) code developed by the Wisconsin Solar Energy Laboratory as the ‘engine’ for 
implementing the array performance models. For weather and solar insolation, SAM uses 
TMY2, TMY3, EnergyPlus Weather (EPW) and METEONORM data. Financial analysis 
capabilities include looking at en ergy costs, financing options, system depreciation, tax 
credits, cash flow, and LCOE. 
Other useful features include the ability to perform sensitivity analysis and optimize 
against a selected output. An internal scripting language is available for custom program 
design and also gives the user the ability to run many simulations. 
Table 1 shows the many algorithms developed by different authors and available for use 
in SAM. In terms of radiation inputs, the model will accept either beam and diffuse and 
calculate total radiation, or total and beam and calculate diffuse radiation.  
 16 
Table 1.   Algorithm Options in SAM for Solar Radiation, Array and Inverter Performance 
Solar Radiation  Array Performance Inverter 
• Isotropic Sky 
• Hay and 
Davies 
• Reindl 
• Perez et al. 
• Sandia PV array performance model 
(empirical) 
• 5-parameter performance model 
(semi-empirical) 
• PVWatts 
• Simple-efficiency model 
• Sandia inverter performance 
model
 
• Single-point efficiency 
 
A study conducted at S NL by Cameron et al. (2008) compares the output of the three 
array performance models in SAM to output from PVWATTS (Section 2.3.2) and 
PVMOD (Section 2.2.6). The paper also compared the output of the different solar 
radiation models used within SAM and the simplified PVMOD version. The study 
showed similar predictions of monthly performance of crystalline silicon systems when 
modeled annual output was normalized to measured annual output. However for non -
crystalline technologies the percentage difference bet ween each model’s outputs was 
often much higher. 
Availability and Maintenance 
SAM was created in 2006 and is maintained by NREL. The program can be downloaded 
at 
https://www.nrel.gov/analysis/sam/. A major upgrade to the software occurred in 2009 
and the version available at the time of this report is 2009.10.2. 
References 
• Mehos, M., and D. Mooney, 2005, Performance and Cost Model for Solar Energy 
Technologies in Support of the Systems-Driven Approach, NREL/CP-550-37085. 
National Renewable Energy Laboratory, Golden, CO, January 2005. 
• Cameron, C. P., W. E. Boyson, D. M. Riley, 2008, Comparison of PV System 
Performance-Model Predictions with Measured PV System Performance, 33rd 
IEEE PVSC, San Diego, CA, May 12-16, 2008. Available at: 
https://www.nrel.gov/analysis/sam/pdfs/2008_sandia_ieee_pvsc.pdf  
• Gilman, P., N. Blair, M. Mehos, C. Christensen, S. Janzou, and C. Cameron, 
2008, Solar Advisor Model User Guide for Version 2.0, NREL/TP-670-43704. 
National Renewable Energy Laboratory, Golden, CO, August 2008. 
• Additional SAM-related publications are available at: 
https://www.nrel.gov/analysis/sam/publications.html 
 17 
2.3 Other PV Performance Models 
2.3.1 5-Parameter Array Performance Model 
Description 
The 5-Parameter array performance model was developed from research conducted at the 
Wisconsin Solar Energy Laboratory (SEL). This model utilizes the well known one-diode 
array performance model for evaluating PV array performance.  It was initially descri bed 
as the 4 -parameter or equivalent one- diode model by Townsend (1989). The model was 
incorporated into TRNSYS by Eckstein (1990), and is described by Duffie and Beckman 
(1991). Further validation and analysis by DeSoto (2004) at the SEL led to the 5-
parameter version (DeSoto et al., 2006). In general, like the Sandia PV Array 
Performance Model, the 5-parameter model was developed to better predict power output 
from PV under non-standard test conditions. 
The 5 -parameter model was intended to predict both m aximum power and current -
voltage characteristics using only data normally supplied by manufacturers.  At the time 
of model development, manufacturers typically supplied values of: short circuit current, 
open circuit voltage, voltage at maximum power point, current at maximum power point, 
and the temperature coefficients of both open circuit voltage and short circuit current.  
This available data was then used to determine the ideality factor, light current, diode 
reverse saturation current, series resistanc e, and shunt resistance (DeSoto et al., 2006). It 
is considered a semi -empirical model as some of these 5 parameters are theoretical and 
some are calculated from known relationships and equations derived from previous 
studies. When shunt resistance is very  high, its impact tends to be very small and the 
model is then described as a 4 -parameter model. This model can be used to predict 
performance for cSi, ribbon cSi, and thin film (CdTe, and aSi), however work is currently 
underway to improve the model accuracy for the thin-film technologies. 
This algorithm is one of four implemented in the SAM system program as described 
above in Section 2.2.9. The California Energy Commission (CEC) uses the 5- parameter 
model and an inverter model to estimate system performa nce for the New Solar Homes 
Partnership (NSHP) program.  The estimated performance is used to determine the state 
rebate to the homeowners This NSHP program is only for new houses in the State of 
California.  
Availability and Maintenance 
The 5 -parameter mo del is constantly evolving from its inception in 1989 to its most 
current version as implemented in SAM and the CEC models. Additional work is being 
done at the SEL to improve the model for analyzing thin-film modules. 
The 5-parameter model is available as a free download at: 
http://sel.me.wisc.edu/software.shtml   
The CEC implementation of the 5-paramater model is available at: 
http://www.gosolarcalifornia.org/nshpcalculator/index.html  
 18 
The 5-parameter model is implemented in SAM: 
https://www.nrel.gov/analysis/sam/ 
References 
• Townsend, T. U., 1989, A Method for Estimating the Long-Term Performance of 
Direct-Coupled Photovoltaic Systems, M.S. thesis, University of Wisconsin-
Madison, Madison, WI. Available at: 
http://sel.me.wisc.edu/theses/townsend89.zip  
• Eckstein, J. H., 1990, Detailed Modeling of Photovoltaic System Components, 
M.S. thesis, University of Wisconsin-Madison, Madison, WI. Available at: 
http://sel.me.wisc.edu/theses/eckstein90.zip  
• Duffie, J. A. and W. A. Beckman, 1991, Solar Engineering of Thermal Processes, 
Second Edition, John Wiley & Sons, Inc., New York, NY. 
• DeSoto, W., 2004, Improvement and Validation of a Model for Photovoltaic 
Array performance, M.S. thesis, University of Wisconsin-Madison, Madison, WI. 
Available at: http://sel.me.wisc.edu/theses/desoto04.zip.  
• DeSoto, W., S. A. Klein, and W. A. Beckman, 2006, Improvement and Validation 
of a Model for Photovoltaic Array performance, Solar Energy, Vol. 80, No. 1, pp. 
71-80. 
2.3.2 PVWatts 
Description 
PVWatts is a grid -connected photovoltaic modeling tool developed by NREL that is 
based on the PVForm algorithms developed at  SNL (Section 2.2.4). This  includes the 
POA radiation mode l (Perez et al. 1987, 1988) and the modified power temperature 
coefficient model for array performance. A hierarchy of programs that descended from 
PVForm and from its predecessor, PVWatts is shown above in Figure 2.  
PVWatts is available as a web -based ap plication in two different versions. Version 1 
allows the user to choose from preset locations and PV system values that include the DC 
rating, derate factors, array type (fixed tilt, 1 -axis or 2 -axis tracking), array tilt and 
azimuth. It also  assumes -0.5%/C which is reasonable for cSi but not for  thin-film 
technology. 
Output includes monthly averages of solar radiation, AC energy and the energy value 
(kWh x cost/kWh) all of which can be exported on an hourly basis. Version 2 uses an 
internet map server (I MS) to allow the user to choose a more site -specific location than 
what is available in version 1. The user can zoom in on an area, click on the PVWatts 
icon, then click on a desired grid cell. The same input parameter window from version 1 
appears and the user can input the parameters described above. 
 19 
NREL recently created a program called In My Backyard (IMBY) that runs on the 
PVWatts platform and allows a user to zoom in on a specific location and draw a shape 
that resembles the outline of a PV array. This specific area is translated into a system size 
in kilowatts with a default derating factor, latitude tilt and assumed azimuth angle of 180 
degrees. The model uses Perez satellite derived radiation input. Output includes the 
standard PVWatts information with added information on system payback and the ability 
to change all input variables for a more customized output. The user can then compare 
generation with electricity consumption by uploading a load profile and also compare 
monthly electric bills before and after PV installation based on electric rates. Geographic 
coverage includes North America, Central America and the northern extents of South 
America. 
PVWatts is also used in the California Solar Initiative (CSI) EPBB Calculator to 
determine incentives for PV on existing buildings (See discussion of a different 
California benefit calculator for new homes in Section 2.3.1 above).  
Availability and Maintenance 
PVWatts is available in two versions. Version one can be used to evaluate system output 
for locations around the world: 
http://www.nrel.gov/rredc/pvwatts/version1.html   
Version 2 is for the U.S. and its territories and can provide more site -specific 
meteorological input than version 1: http://www.nrel.gov/rredc/pvwatts/version2.html  
The IMBY tool is available at: http://www.nrel.gov/eis/imby/ 
The CSI EPBB Calculator can be found at: http://www.csi-epbb.com/default.aspx   
References 
• Marion, B., M. Anderberg, P. Gray-Hann, and D. Heimiller, 2001, PVWATTS 
Version 2 – Enhanced Spatial Resolution for Calculating Grid-Connected PV 
Performance: Preprint, NREL/CP-560-30941. National Renewable Energy 
Laboratory, Golden, CO, October 2001. 
• Marion, B., M. Anderberg, and P. Gray-Hann, 2005, Recent and Planned 
Enhancements for PVWATTS, NREL/CP-520-38975. National Renewable Energy 
Laboratory, Golden, CO, November 2005. 
2.3.3 PVSYST 
Description 
PVSYST is a photovoltaic system analysis software program de veloped by the Energy 
Group at the University of Geneva in Switzerland and can be used at any location that has 
meteorological and solar insolation data. It is widely used due to the many parameters 
available for the user to modify. The complexity of the input parameters makes it suitable 
for expert users.  
 20 
For POA radiation, the default is the Hay (1979) model, however the user can also 
specify the Perez et al. (1987, 1988) model. PVSYST uses the one -diode equivalent 
circuit model for calculating performan ce in cSi and HIT modules, and a modified 
version for what they consider “stabilized” thin film modules, such as aSi, CiS and CdTe. 
The program allows input from many different weather and solar insolation datasets, 
including Meteonorm, Satellight, TMY2/3, ISM-EMPA, Helioclim- 1 and - 3, NASA-
SSE, WRDC, PVGIS- ESRA and RETScreen. There is also a custom input option that 
allows for importing the required data from a comma -separated value (csv) file format. 
PVSYST can work with many different currencies from around the world, and can model 
system lifecycle costs, financing, and feed-in tariffs. 
Other interesting features include a 3-D shading tool that allows a user to draw a structure 
with PV arrays and see potential shading impacts from simulated obstructions. There is 
an option to analyze array mismatch to determine more specific Isc and Voc parameters, 
as well as look at cell/module shading and other voltage losses due to wiring, and soiling. 
Other useful features include an incident angle modifier and an air mass spectral 
correction for thin- film modules, as well as the ability for the user to input known 
parameters and coefficients if measured data is available for both PV modules and 
inverters. 
Availability and Maintenance 
PVSYST is available at the followin g website: 
http://www.pvsyst.com/ch/index.php. A 
15-day trial version can be downloaded for evaluation purposes. It appears the software 
was developed in the mid- 1990s, though the exact date is unknow n. The most recent 
version (5.05) was released in late 2009. 
References 
• Mermoud, A., 1995, Use and Validation of PVSYST, A User-Friendly Software 
for PV-system Design, 13th European Photovoltaic Solar Energy Conference, 
Nice, France, October 23-27, 1995. 
• Van der Borg, J. J. C. M., and M. J. Jansen, 2003, Energy Loss Due to Shading in 
a BIPV Application, 3rd World Conference on Photovoltaic Energy Conversion, 
Osaka, Japan, May 11-18, 2003. Available at: 
http://www.ecn.nl/docs/library/report/2003/rx03024.pdf  
2.3.4 PV F-Chart 
Description 
PV F-Chart is a PV array performance modeling software developed at the University of 
Wisconsin SEL and licensed through F-Chart software.  
For POA radiation, it uses a simple isotropic sky model (Liu and Jordan, 1963). Array 
performance of cSi modules is calculated as a function of cell temperature, efficiency, 
and incident angle. For weather and solar insolation, TMY2 data is utilized. Economic 
analysis results including life-cycle and equipment costs are also included in the analysis. 
 21 
Equations used for radiation analysis and array performance are provided in a literature 
review of PV F-Chart completed by Texas A&M in 2004. 
Availability and Maintenance 
PV F -Chart is a commercial software product available from F -Chart software: 
http://www.fchart.com/pvfchart/pvfchart.shtml. The program was created in 1985 and the 
last update to this software appears to be in 2001.  
A demonstration version is available at: 
http://www.fchart.com/pvfchart/pvfchartdemo.shtml  
The user manual is available at: http://www.fchart.com/download/pvfchart_manual.exe  
References 
• Evans, D. L., W. A. Facinelli and R. T. Otterbein, 1978, Combined 
Photovoltaic/Thermal System Studies, SAND78-7031. Sandia National 
Laboratories, Albuquerque, NM, August 1978. 
• Siegel, M. D., S. A. Klein, and W. A. Beckman, 1981, A Simplified Method for 
Estimating the Monthly-Average Performance of Photovoltaic Systems, Solar 
Energy, Vol. 26, No. 5, pp. 413-418. 
• Clark, D. R., S. A. Klein, W. A. Beckman, 1984, A Method for Estimating the 
Performance of Photovoltaic Systems, Solar Energy, Vol. 33, No. 6, pp. 551-555. 
• Publications describing the use of and outputs from PV F-Chart are available at 
the SEL publications page: http://sel.me.wisc.edu/publications.shtml  
• A detailed history of PV F-Chart and the equations drawn upon by other 
researchers is provided in a report by the Texas A&M Energy Systems Laboratory 
for the Texas Commission on Environmental Quality, available at:  
http://repository.tamu.edu/handle/1969.1/2069  
2.3.5 RETScreen Photovoltaic Project Model 
Description 
RETScreen is a program developed by Natural Resources Canada for evaluating both 
financial and environmental costs and benefits for many different renewable energy 
technologies. RETScreen has a specific Photovoltaic Project Model that can model PV 
array performance for many locations around the world.  
For POA radiation, it uses a simple isotropic sky model (Liu and Jordan, 1963). The array 
performance model used by RETScreen is based on the power temperature coefficient 
model by Evans (1981) ( Section 2.2.3). The software has the ability to model many 
different types of PV modules including cSi, CdTe CiS and aSi. For weather and 
 22 
insolation data, it can use TMY2 and NASA -SSE. Financial output includes project cost 
and savings, financial feasibility and lifecycle cash flows. 
Availability and Maintenance 
It appears that RETScreen was developed around 1997. RETScreen v4 was last updated 
in 2009 and is the most recent version at the time of this report. It runs within Microsoft 
Excel and can be downloaded at the following location: 
http://www.retscreen.net/ang/home.php  
References 
• Evans, D. L., 1981, Simplified Method for Prediction Photovoltaic Array Output, 
Solar Energy, Vol. 27, No. 6, pp. 555-560. 
• Braun, J. E., and J. C. Mitchell, 1983, Solar Geometry for Fixed and Tracking 
Surfaces, Solar Energy, Vol. 31, No.5, pp. 439-444. 
• Duffie, J. A. and W. A. Beckman, 1991, Solar Engineering of Thermal Processes, 
Second Edition, John Wiley & Sons, Inc., New York, NY. 
• Equations used in developing the PV Project Model for RetScreen can be found 
at: http://www.retscreen.net/ang/textbook_pv.html  
• General references for tutorials and case studies are available at:  
http://www.retscreen.net/ang/g_photo.php  
2.3.6 PVSol 
Description 
PVSol is a photovoltaic systems analysis software program developed by Valentin 
Energy Software in Germany with an English language version distributed by the Solar 
Design Company based in the UK. The first version of PVSol was released in 1998. The 
Expert edition has the most features, including a 3-D shading program. 
For POA radiation, it uses the Hay and Davies (Davies and Hay, 1980) anisot ropic sky 
model. Array performance is calculated as a function of incoming irradiance, module 
voltage at STC and an efficiency characteristic curve. PVSol can use either a linear or 
dynamic temperature model. There is also an incident angle modifier for de termining 
how much is radiation is reflected. The software can model performance for the 
following PV technologies: cSi, CdTe, CiS, aSi, HIT, µc -Si, and Ribbon. For insolation 
and weather data, the program uses MeteoSyn, Meteonorm, PVGIS, NASA SSE, 
SWERA a nd custom inputs. The software has a great deal of economic analysis 
capabilities, including determining economic efficiency for cash value, capital value, 
amortization and electricity production costs. As with other PV software programs 
developed in Europe, feed-in tariffs can be incorporated.    
 23 
Availability and Maintenance 
PVSol is a commercial software product maintained by Valentin Energy Software. The 
most recent version of PVSol Expert 4.0 was released in 2009. According to the Solar 
Design Company, an English language version of Expert will be available in late 2009.  
 
A limited feature demo version is available for download:  
http://www.solardesign.co.uk/index.htm  
PVSol is also available at:  
http://www.valentin.de/  
References 
• An internet search of PVSol brings up journal articles of system modeling 
applications primarily applied in Europe. 
2.3.7 Polysun 
Description 
Polysun is a photovoltaic systems analysis software program designed by Vela Solaris in 
Switzerland. The company began operation in 2007 and started releasing its software to 
U.S. customers in May 2009. The program does not give any detail on what type of POA 
radiation or array performance models a re used in the calculations. The software can 
model performance from the following PV modules: cSi, CdTe, CiS, aSi, HIT, µc-Si, and 
Ribbon. For insolation and weather data, the program uses Meteotest. Economic analysis 
includes financing, operations and m aintenance (O&M) costs, incentives, energy prices, 
fuel cost savings and system value. 
Availability and Maintenance 
Polysun is a commercial software program available from Vela Solaris . The most recent 
version available is 5.2. 
A limited feature demo version is available for download: 
http://www.velasolaris.com  
References 
• An internet search of Polysun brings up journal articles of system modeling 
applications primarily applied in Europe. 
2.3.8 INSEL 
Description 
The Integrated Simulation Environment Language (INSEL) solar electricity toolbox from 
Doppelintegral GmbH in Germany is a photovoltaic systems analysis program. It appears 
the software was initially developed in 1991. INSEL is modular in the sense that it can be 
linked to other programs and can be customized by an advanced user. 
 
 24 
INSEL gives users 10 options for radiation conversion on a tilted surface and include: 1) 
Isotropic Sky (Liu and Jordan, 1963), 2) Temps and Coulson (1977), 3) Bugler (1977), 
Hay and Kambezidis, 4) Klucher (1978), 5) Hay (1979), 6) Willmott (1982), 7) Skartveit 
and Olseth (1986), 8) Gueymard (1987), 9) Perez et al. (1987, 1988), and 10) Reindl 
(1988). For PV performance modeling, INSEL uses a one -diode or modified two- diode 
model as described by Obst (1994) and Jakobides (2000). There are four different options 
for modeling incident angle losses. A module thermal model is used to describe heat gain 
and loss. Modules that can be utilized include cSi; however other technologies such as 
thin-film are probably in the database. For insolation and weather data, the program uses 
its own weather database. Economic analysis includes installed system cost, O&M  costs, 
net-present value (NPV), electricity costs and feed-in tariffs. 
Availability and Maintenance 
INSEL version 8.0 pre -release was released in late 2009 at the time of this report and is 
available for a free 30-day trial version: 
http://www.insel.eu/index.php?id=79&L=1 
References 
• Obst, C., 1994, Kennlinienmessung an Installierten Photovoltaik-Generatoren 
und deren Bewertung, M.S. thesis, University of Oldenburg, Germany. 
• Jakobides, F., 2001, Nutzung empirischer Datensätze zur Bestimmung der 
Modellparameter für Solarzellen auf der Basis von kristallinem und amorphen 
Silizium, M.S. thesis, Fachhochschule Magdeburg, Germany. Available at: 
http://www.insel.eu/fileadmin/insel.eu/diverseDokumente/Diplomarbeit_Fr.Jabob
ides.pdf   
• A general list of publications using INSEL can be found at: 
http://www.insel.eu/index.php?id=40&L=1  
• Equation descriptions are available at: 
http://www.insel.eu/fileadmin/insel.eu/softwareLE/inselBlockReference.pdf  
• Calculations for incoming solar radiation module are available at: 
http://www.insel.eu/fileadmin/insel.eu/diverseDokumente/inselTutorial/module09
.pdf  
• Examples of grid-connected and off-grid battery storage applications are available 
at: 
http://www.insel.eu/fileadmin/insel.eu/diverseDokumente/inselTutorial/module10
.pdf  
2.3.9 SolarPro 
Description 
SolarPro software is a PV system simulation program from Laplace System based in 
Kyoto, Japan. The first version of the software appears to have been released in 1997. 
 25 
The user must first define the system in terms of mounting, array layout and  orientation, 
then develop a 3 -D layout that  can have shading object s built -in. Interesting features 
include detailed analysis of module -specific shading within an array by looking at 
module I-V curves. 
Based on the demonstration version, it is not clear what type of radiation processor or 
POA radiation algorithm is used. It appears that the one-diode equivalent circuit model is 
used to calculate array performance. Temperature effects are modeled as a function of 
temperature, irradiance and wind speed. System derates are lumped into one coefficient 
for soiling and electrical losses. Inverter losses are determined by an inverter specific 
efficiency, which can be changed. Based on the module database for the demonstration 
version, cSi, thin-film (aSi, CdTe), and HIT modules can be utilized, as well as the ability 
to input user -defined modules. System construction and O&M costs can be included in 
the analysis. 
Availability and Maintenance 
The most recent version of SolarPro is 3.0. It appears to be maintained and updated and is 
available in an English language version. The softw are is available for a 90 -day trial 
version. 
http://www.lapsys.co.jp/english/  
References 
• The software is available at: http://www.lapsys.co.jp/english/ 
2.4 Simplified PV Performance Models  
2.4.1 Clean Power Estimator 
Description 
Clean Power Estimator (CPE) is a customizable web -based PV system and financial 
analysis program. It can be tailored by Clean Power Research to provide a site specific 
interface that can be designed as a quick look at system performance and financial 
analysis for a PV system. This tool is marketed to the consumer who wants an easy to use 
program with a minimal number of inputs. The array performance and POA algorithms 
are based on S NL’s PVForm code (Section 2.2.4) and has been tested and validated by 
the Clean Power Research Company. For insolation and weather data, CPE uses TMY2 
as well as proprietary satellite based estimates of insolation. Financial analysis includes 
system financing, payback, cash flow, O&M and depreciation. 
Availability and Maintenance 
Clean Power Research can provide a customized web -based tool for specific customers 
and is used in many locations around the U.S.: 
http://www.cleanpower.com/  
 
An example of a specific application developed for the State of California is the CEC 
Clean Power Estimator:  
http://cec.cleanpowerestimator.com/cec.htm  
 26 
A CPE application built for the state of New York is available at: 
 http://nyserda.cleanpowerestimator.com/nyserda.htm  
References 
• Clean Power Estimator provides reports describing the use and application of its 
software. A paper that describes the array performance portion “Validation of a 
Simplified PV Simulation Engine” can be found at: http://www.clean-
power.com/research/customerPV/PVModelValidation.pdf  
2.4.2 PVOptimize 
Description 
PVOptimize is a software tool developed for the California market by KGA Associates 
and is geared towards installers for generating system quotes and design.  
The program uses PVWatts (Section 2.3.2) for solar resource data and array performance 
modeling. Modules available for analysis include cSi, CdTe, aSi, CPV and Ribbon. For 
weather and insolation, the program uses PVWatts (TMY2) data. There are many forms 
and inputs specific to the incentives and rebates offered by the State of California. 
Therefore the model may have limited utility to locations outside of California. 
Availability and Maintenance 
PVOptimize is a commercial software program from KGA Associates, LLC. A 7 -day 
trial version is available for evaluation purposes. 
References 
• 
http://www.pvoptimize.com/index.html 
2.4.3 OnGrid 
Description 
OnGrid is a software tool developed for use in the U.S. by Andy Black of OnGrid Solar 
in California and is focused on what installers need for system quotes and design.  
The program uses PVWatts (Section 2.3.2) for the array performance calculations. 
Module technologies available for analysis include cSi, aSi, CdTe and Ribbon. This 
software consists of a macro -enabled Excel spreadsheet that can be customized for any 
incentive program available in the U.S. Incentives for the State of California are included 
by default. The spreadsheet can look at system cost, incentives, depreciation, cash flow, 
O&M costs, and internal rate of return. 
Availability and Maintenance 
A time -limited demonstration version along with monthly or annual subscriptions is  
available at: 
http://www.ongrid.net/payback/signup.html  
 27 
References 
• The software developer has a link to many papers and presentations that discuss 
the use of OnGrid for system sizing and PV economics. 
http://www.ongrid.net/papers/index.html  
2.4.4 CPF Tools 
Description 
CPF Tools is a software program developed in 2007 by Energy Matters LLC for Clean 
Power Finance. The software is aimed towards system installers for system design, 
economics and financing. CPF tools also leverages the technology in RoofRay, which is 
an on-line interactive tool that allows a user to easily draw an outline of a potential PV 
array to explore the potential costs and benefits. RoofRay is similar to the IMBY tool 
developed by NREL for an interactive analysis of potential PV system size (Section 
2.3.2).  CPF Tools was previously known as Solar Pro Tools. 
For array performance, CPF Tools uses PVWatts. Module technologies available for 
analysis include cSi, aSi, CdTe and Ribbon. Insolation and weather data are taken from 
the NCDC U.S. Historical Climatology Network (USHCN). 
Availability and Maintenance 
CPF Tools is available for download on the internet . At  the time of this report, the 
company has a variety of subscription plans for customers. According to Energy Matters 
LLC, the next generation of the software will be called Energy Periscope. 
A 7-day trial version is available for evaluation at: 
http://www.cleanpowerfinance.com/solar/installer-tools/pricing/   
References 
• See software description at: http://www.cleanpowerfinance.com/  
• Next version of software: http://www.energyperiscope.com/   
• RoofRay is available at: http://www.roofray.com/   
2.4.5 Solar Estimate 
Description 
Solar Estimate is a web-based tool developed by Energy Matters LLC for both residential 
and commercial solar resource estimation. The user enters in a zip code and chooses the 
utility that they purchase power from. Assumptions include a total energy delivered of 
78%, which includes derates for panel, inverter, wiring and panel soiling. For POA 
radiation and array performance, PVWatts is used. The model does not specify a PV 
technology, although it is likely based on flat plate cSi modules. Because the model uses 
PVWatts for determining solar energy, it probably  uses TMY2 data for weather and 
insolation measurements. 
 28 
Output includes an estimated system size, cost, financial incentives based on location and 
utility, cash flow, and savings and benefits over system lifetime. Assumptions used in the 
model are available for the user to review at the end of the “Your Solar Electric Estimate” 
page. 
Availability and Maintenance 
Solar Estimate was developed in 2000 and is currently maintained and updated to take 
advantage of the many local, state and federal tax credits and incentives that are available 
to residential and commercial customers. Because it is web -based, there is nothi ng to 
download.  
References 
• Solar Estimate is available at: 
http://www.solar-estimate.org/   
3. Hybrid System Models 
Hybrid system models are used to simulate the performance of “hybrid” or “distributed 
energy resource” systems that typically include one or more renewable sources of 
electricity combined with a traditional fossil based fuel source. These models were built 
initially to look at the use of PV or wind as a backup source for small and remote off -grid 
applications. Battery storage and lifetime (primarily from lead -acid) is simulated due to 
the need for a continuous source of power. More recent models can incorporate sources 
such as biomass, hydro, and other energy storage devices such as non lead -acid batteries, 
fuel cells, capacitors, flywheels and compressed air. These models can also look at grid -
tied systems and attempt to capture interactions at the utility scale. 
The International Energy Agency  (IEA) is funding a program through the Photovoltaic 
Power Systems Programme (PVPS) as Task 11 –  PV Hybrids and Mini Grids as a multi -
year project that started in 2006 and will continue until 2011. Their research aims to 
document the many hybrid system models and compare their structure, inputs and 
outputs. More specifically, the IEA is looking at market penetration and technical issues 
surrounding PV -hybrid systems. This work can be viewed at: 
http://www.iea-pvps-
task11.org/. The models described below that are a p art of this research effort include: 
Homer, ViPOR, Hybrid2, RetScreen, IPSYS, ISE, and HySys.  
Hybrid system modeling is becoming more important as the idea of microgrid generation 
and delivery in a grid-tied system becomes a more recognized and adopted infrastructure. 
Microgrids are the integration of hybrid systems to an existing grid -tied infrastructure, or 
in other cases, a more complex off -grid system. Recent reports from the DOE’s 
Renewable Systems Interconnection Study (RSI) by Whitaker et al. (2008)  and Ortmeyer 
et al. (2008) address the possible issues arising from high penetration of PV in distributed 
generation and microgrid applications. This paper does not discuss microgrid system 
models and needs as those are addressed in detail by Ortmeyer et al. (2008). 
 
 29 
      
 
Figure 3.  Illustration of a Hybrid Electric Power System  
 
3.1 Hybrid System Models Developed and Used by Sandia 
National Laboratories 
3.1.1 SOLSTOR 
Description 
SOLSTOR is a model developed at SNL for looking at the overall economics and 
optimization strategies of different hybrid system configurations. Components include 
PV arrays, wind turbines and generators. Storage is in the form of batteries and 
flywheels. Power conditioning options are also available. The model can be run with a 
utility connection or stand-alone with a backup generator.  
The program incorporates some of the PV array performance algorithms as described in 
SOLCEL (Section 2.2.2). PV technologies that can be modeled include cSi and CPV. 
SOLSTOR uses the SOLMET database for weather and insolation data. Economic output 
includes capital costs, O&M costs, energy purchase costs, depreciation, investment tax 
credits, salvage value and financing. 
Availability and Maintenance 
SOLSTOR was  developed and used in the 1979- 1982 timeframe. It was written in 
Fortran77 and is no longer used or maintained by researchers at SNL. The equations used 
in the program are documented by Aronson et al. (1981) and Aronson et al. (1982). 

 30 
References 
• Aronson, E. A., D. L. Caskey and B. C. Caskey, 1981, SOLSTOR Description and 
User’s Guide, SAND79-2330. Sandia National Laboratories, Albuquerque, NM, 
March 1981. 
• Caskey, D. L, E. A. Aronson, and K. D. Murphy, 1981, Parametric Analysis of 
Stand-Alone Residential Photovoltaic Systems and the SOLSTOR Simulation 
Model, 15
th IEEE PVSC, Kissimmee, FL, May 12-15, 1981. [SAND81-1130C] 
• Aronson, E. A., D. L. Caskey and K. D. Murphy, 1982, SOLSTOR II Description 
and User’s Guide, SAND82-0188. Sandia National Laboratories, Albuquerque, 
NM, June 1982. 
3.1.2 HybSim 
Description 
HybSim is a hybrid energy simulator deve loped and copyrighted at SNL for looking at 
the costs and benefits of adding renewable energy to a fossil fueled electrical generation 
system in a remote location. The mo del requires knowledge of the existing load profile, 
weather, battery characteristics and a few economic details. At the moment, solar PV is 
the only renewable energy source available for comparison however wind power will be 
another choice in a future ver sions of the model. Current license holders include the 
University of Michigan and a few corporate customers. 
The system is designed to model cSi modules. For weather and insolation, HybSim can 
use data measured  at 15 -minute intervals. Lifecycle costs are analyzed for system 
components including PV modules, generators and batteries. Capabilities include 
comparing cost and performance differences with a diesel only system with one using a 
combination of diesel, PV, wind and battery storage. 
Availability and Maintenance 
HybSim version 1 (2005) is currently available for license from SNL . At the time of this 
report, the model is still undergoing development to add additional features. See the 
intellectual property available for licensing (IPAL) site for detail on how to license 
HybSim: 
http://ipal.sandia.gov/Default.php.  
References 
• Kendrick, L., J. Pihl, I. Weinstock, D. Meiners, and D. Trujillo, 2003, Hybrid 
Generation Model Simulator (HYBSIM), EESAT Conference, San Francisco, CA, 
October 27-29, 2003. [SAND2003-3790A] 
3.1.3 Hysim 
Description 
Hysim is a hybrid energy simulation model developed at SNL for analyzing the 
combination of PV , diesel generators and battery storage for stand- alone systems in 
 31 
remote locations. The purpose of this model was to look at increasing overall system 
reliability by adding the PV and battery storage, as well as the economics associated with 
PV and batter ies compared to existing generator only systems. Hysim uses a modified 
version of the battery model in SOLCEL (Section 2.2.2). 
For POA radiation and PV array performance, Hysim uses PVForm (Section 2.2.4). The 
only PV technology modeled in Hysim is cSi. For weather and insolation data, Hysim 
uses TMY2. Financial analysis includes LCOE, lifecycle, fuel and O&M costs, as well as 
cost comparisons between different configurations. 
Availability and Maintenance 
Hysim was developed around 1987 and appears to have been used up until 1996. It is not 
currently being used, supported or updated by researchers at SNL . Those interested in 
this hybrid simulator should see the references below for more information. 
References 
• Jones, G. J., and R. N. Chapman, 1987, Photovoltaic/Diesel Hybrid Systems: The 
Design Process, 19
th IEEE PVSC, New Orleans, LA, May 4-8, 1987. [SAND87-
1203C] 
• Chapman, R. N., 1996, Hybrid Power Technology for Remote Military Facilities, 
Powersystems World ’96, Las Vegas, NV, September 7-13, 1996. [SAND96-
1867C]  
3.2 Other Hybrid System Models 
3.2.1 HOMER 
Description 
HOMER is a hybrid system model developed at NREL in 1993 for both on-grid and off-
grid systems. A unique capability that HOMER offers is the ability to find the optimal 
configuration based on price estimates as well as perform sensitivity analysis to help 
understand tradeoffs between different technologies and economic considerations. The 
software has the ability to compare multiple system configurations as well as different 
battery types. HOMER uses the KiBaM code for battery life modeling as described below 
in Section 4.2.1. The model can incorporate the following components: PV, wind, hydro, 
fossil fuel generator, battery, AC/DC converter, electrolyzer, hydrogen tank and 
reformer. The loads that it can simulate include primary, deferrable, thermal and 
hydrogen.  
POA radiation is modeled using the HDKR model (Duffie and  Beckman, 1991). For PV 
array performance, the program uses an equation that describes power output as function 
of incident radiation. Temperature effects are not considered in the performance 
calculation, however they can be accounted for as a part of the  total system derate. 
HOMER uses a generic module type for analysis. For weather and insolation, HOMER 
can use TMY2 formatted data or custom user inputs. 
 32 
The help file within the program describes each calculation and its reference, if available.  
Availability and Maintenance 
HOMER is maintained by HOMER Energy (as of 2009) and the most current version of 
the program (2.67) is available for download at: http://www.homerenergy.com/. 
According to HOMER Energy, future versions will have an associated cost.   
References 
• Documentation is available at: http://www.homerenergy.com/documentation.asp  
• A HOMER bibliography of publications compiled by NREL is available at: 
http://www.homerenergy.com/pdf/HOMERPublications.pdf  
3.2.2 Hybrid2 
Description 
Hybrid2 is described as a probabilistic time series computer model for evaluating the 
performance and economics of hybrid electricity generating systems. It was developed by 
the Renewable Energy Research Laboratory (RERL) at the University of Massachusetts 
Amherst with support from NREL. This program is an engineering design model for 
hybrid systems consisting of PV , wind, generators and battery storage for both on- grid 
and off-grid systems.  
For POA radiation, the model uses the HDKR model (Duffie and Beckman, 1991). For 
PV array performance, Hybrid 2 uses a version of the 5- parameter model developed by 
SEL as described in Section 2.3.1. Module technologies that can be modeled include cSi, 
CdTe, CiS and aSi. The format for weather and insolation data is unknown. Financial 
analysis includes lifecycle cost, cash flow, NPV, payback, internal rate-of-return (IRR) as 
well as tradeoffs between different hybrid system configurations. 
Availability and Maintenance 
Hybrid2 was initially developed in 1994 as Hybrid1, then as Hybrid2 in 1996. The most 
current version is 1.3e (2004). At this time, there are no plans to update the model past 
the current version. Hybrid2 is maintained by the RERL and can be downloaded at: 
http://www.ceere.org/rerl/projects/software/hybrid2/  
References 
• A list of publications related to Hybrid2 is available at: 
http://www.ceere.org/rerl/rerl_publications.html  
• A detailed theory manual with software description and equations is available at: 
http://www.ceere.org/rerl/projects/software/hybrid2/Hy2_theory_manual.pdf  
 33 
3.2.3 UW-Hybrid (TRNSYS) 
Description 
The UW-Hybrid simulation model is described as a quasi- steady performance simulation 
tool for looking at hybrid systems consisting of solar, wind, diesel generators and battery 
storage. This hybrid simulator is part of the TRNSYS software program but can be run 
alone under a demonstration editor version called TRNSED. 
Running the hybrid model in TRNSYS, POA radiation models include simple isotropic 
sky (Liu and Jordan, 1963), Hay and Davies (Davies and Hay, 1980), Reindl (1988) and 
Perez et al. (1987, 1988) For array performance, TRNSYS uses the 5- parameter array 
performance model (Section 2.3.1). PV technologies include cSi, CPV and aSi. Weather 
and insolation data includes TMY, TMY2, Meteonorm, EnergyPlus and the International 
Weather for Energy Calculations (IWEC) database.  
Availability and Maintenance 
UW-Hybrid as i mplemented under TRNSED is available from the SEL at: 
http://sel.me.wisc.edu/trnsys/downloads/trnsedapps/demos.htm. The program was written 
in 1998 under TRNSYS version 14.2 and there are not many manufacturer options for the 
PV array, wind turbine, generator or battery. More detailed information is likely to be 
included in the most recent version of TRNSYS.  
An evaluation version of TRNSYS is available at:  
http://sel.me.wisc.edu/trnsys/downloads/#EvaluationVersion.  
Details about the full version of TRNSYS can be found at: 
http://sel.me.wisc.edu/trnsys/default.htm  
References 
• Detailed references and publications using TRNSYS for hybrid system modeling 
can be found at: http://sel.me.wisc.edu/publications.shtml.  
3.2.4 RETScreen 
Description 
RETScreen is a program developed by Natural Resources Canada for evaluating both 
financial and environmental costs and benefits for many different renewable energy 
technologies for any location in the world. The Photovoltaic Project Analysis module was 
covered in Section 2.3.5. Electricity generation options include solar, wind, fuel cells, gas 
or diesel generators, gas turbines, geothermal, tidal power, wave power, hydro turbine, 
and ocean current power. For combustible fuels, fossil, biomass, waste and hydrogen are 
listed in terms of inputs for modeling. Energy storage options include batteries. 
For POA radiation, it uses a simple isotropic sky model (Liu and Jordan, 1963). The array 
performance model used by RETScreen is based on the power temperature coefficient 
model by Evans (1981). The software has the ability to model many different types of PV 
modules including cSi, CdTe CIS and aSi. For weather and insolation data, it can use 
 34 
TMY2 and NASA -SSE. Financial output includes project cost and savings, financial 
feasibility and lifecycle cash flows. 
Availability and Maintenance 
RETScreen 4 last updated in 2009 is the most recent version at the time of this report. It 
runs within Microsoft Excel and can be downloaded at the following location: 
http://www.retscreen.net/ang/home.php  
References 
• The different power options that can be modeled in RETScreen are discussed at: 
http://www.retscreen.net/ang/power_projects.php  
• RETScreen has an E-Textbook that describes many of the equations for some of 
the different power source options. http://www.retscreen.net/ang/12.php  
• More references are described above in Section 2.3.5 
3.2.5 PVToolbox 
Description 
PVToolbox is a hybrid system model developed for the Natural Resources Canada 
CANMET Energy Technology Centre – Varennes (CETC -Varennes). The program is 
written for use within Matlab Simulink and has been validated using bench tests which 
describe the model vs. measured performance under different load scenarios. The model 
looks specifically at PV, diesel generator and battery systems designed for Canadian 
latitudes and weather conditions.  
It is unknown what type of POA radiation model is used in PVToolbox. PV performance 
is calculated with a one-diode equivalent circuit model similar to that described by Duffie 
and Beckman (1991). PV technologies include cSi and aSi. The format for weath er and 
insolation data inputs is unknown. Financial information includes an O&M calculator for 
lifecycle cost analysis. 
Availability and Maintenance 
This program was likely developed in the early 2000s with updates that appear to have 
been made around 2007. It is unknown if the software is actively being maintained. 
References 
• Duffie, J. A. and W. A. Beckman, 1991, Solar Engineering of Thermal Processes, 
Second Edition, John Wiley & Sons, Inc., New York, NY. 
• Thevenard, D., and M. M. D. Ross, 2002, Validation and Verification of 
Component Models and System Models for the PV Toolbox, Report to CETC-
Varennes (Natural Resources Canada), Varennes, Quebec. Available at: 
http://www.rerinfo.ca/english/publications/pubReport2002PVToolboxValid.html  
 35 
• Ross, M. M. D, 2003, Validation of the PVToolbox Against the First Run of the 
Battery Capacity Cycling Test, Report to CETC-Varennes (Natural Resources 
Canada), Montreal, Quebec. Available at: 
http://www.rerinfo.ca/english/publications/pubReport2003PVTboxValidBCap.ht
ml 
• A comprehensive list of other references including papers and publications 
regarding PV Toolbox is available at the Renewable Energy Research (RER) 
consulting company website: 
http://www.rerinfo.ca/english/publications/all.html  
3.2.6 RAPSIM 
Description 
The Remote Area Power  SIMulator (RAPSIM) is a hybrid system model developed in 
Australia at the Murdoch University Energy Research Institute (MUERI). This program 
simulates systems comprising of PV arrays, wind turbines and diesel generators with 
battery storage. The organization that currently houses the work at the university is called 
the Research Institute for Sustainable Energy (RISE). 
The type of POA radiation and performance models are unknown, as well as modeled PV 
technologies and weather and insolation data inputs. 
Availability and Maintenance 
It appears the software was developed in 1996, with version 2 available in 1997. It is 
unknown if updates have been made to the software. It does not appear the software is 
available for download although references to the program are shown in the link below. 
References 
• Publications describing RAPSIM research performed at the RISE are available at: 
http://www.rise.org.au/pubs/index.html  
• Patel, M. S., and T. L. Pryor, 2001, Monitored Performance Data from a Hybrid 
RAPS System and the Determination of Control Set Points for Simulation Studies, 
ISES 2001 Solar World Congress, Adelaide, Australia, November 25-December 
2, 2001.  
• Jennings, S. U., 1996, Development and Application of a Computerised Design 
Tool for Remote Area Power Supply Systems, Ph.D. dissertation, Murdoch 
University, Perth, Australia. 
3.2.7 SOMES 
Description 
SOMES is also known as the Simulation and Optimization Model for Renewable Energy 
Systems. It was created at the Utrecht University in The Netherlands. The simulation 
program can look at hybrid systems that utilize PV arrays, wind turbines and generators 
 36 
for generating electricity and batteries for storage. Both technical and economic 
parameters can be modeled as well as an optimization model to help figure out the best 
configuration at a specific cost. 
The type of POA radiation and performance models are unknown, as well as modeled PV 
technologies and weather and insolation data inputs. 
Availability and Maintenance 
SOMES was initially developed in 1987 with version 3.0 following in 1993 and version 
3.2 in 1997. It is unknown if the software has been updated past version 3.2. 
References 
• SOMES is described at the following website. It is unclear if the software is still 
available for use or purchase. 
http://www.chem.uu.nl/nws/www/publica/Publicaties%201997/97020.htm  
• SOMES v. 3.2 is also described at: 
http://www.web.co.bw/sib/somes_3_2_description.pdf  
• Van Dijk, V., 1996, Hybrid Photovoltaic Solar Energy Systems, Design, 
Operation, Modelling and Optimization of the Utrecht PBB System, PhD 
dissertation, Utrecht University, The Netherlands. 
3.2.8 IPSYS 
Description 
IPSYS is a hybrid simulation modeling tool for remote systems. The program has a 
component type library and can model electricity generation through PV arrays, wind 
turbines, diesel generators, fuel cells as well as natural gas. Energy storage can be 
modeled using batteries, hydro reservoirs and hydrogen. The model is written in C++ and 
there is no current graphical user interface, however there are scripts that can be used to 
analyze model output within graphs. 
The type of POA radiation and performance models are unknown, as well as modeled PV 
technologies and weather and insolation data inputs. 
Availability and Maintenance 
IPSYS is available from the Riso National Laboratory Wind Energy department. It 
appears the first version  of the software was developed in 2000. It is unclear if the 
software has been updated since 2004. Contact information about the software is 
available at this page: 
http://www.risoe.dtu.dk/research/sustainable_energy/wind_energy/projects/ipsys.aspx?sc
_lang=en 
 37 
References 
• Applications of IPSYS are available at: 
http://www.risoe.dtu.dk/research/sustainable_energy/wind_energy/projects/ipsys.
aspx?sc_lang=en   
• A description of IPSYS as part of the IEA’s PV task 11 can be found at: 
http://www.iea-pvps-task11.org/HTMLobj-167/Gehrke_IPSYS_Valencia08.pdf  
3.2.9 HySys 
Description 
The Hybrid Power System Balance Analyser, or HySys is a hybrid  simulation tool 
developed at the  Centro de Investigaciones Energeticas, Medioambientales y 
Technologicas (CIEMAT) institute in Spain by their wind technology group. The 
software is primarily for isolated systems and includes electricity from PV arrays, wind 
turbines and diesel generators. According to the IEA 2008 report as shown in the 
reference below, the software appears to be under development to operate primarily 
within Matlab.  
The type of POA radiation and performance models are unknown, as well as modeled PV 
technologies and weather and insolation data inputs. 
Availability and Maintenance 
Version 1.0 was developed in 2003. As of 2008, it appears the software is currently being 
used internally by CIEMAT and is undergoing a transition from Excel to Matlab. 
References 
• See link for A. Costa, CIEMAT for a description of the HySys tool:   
http://www.iea-pvps-task11.org/id39.htm  
3.2.10 Dymola/Modelica 
Description 
The Fraunhofer Institute for Solar Energy (ISE)  in Germany uses the Modelica/Dymola 
object oriented programming language for modeling PV -hybrid systems. The electricity 
sources include PV, wind turbines, generators and fuel cells along with storage in the 
form of batteries. 
The type of POA radiation and performance models are unknown, as well as modeled PV 
technologies and weather and insolation data inputs. It appears the program can evaluate 
lifecycle costs and calculate LCOE. 
Availability and Maintenance 
The software development date is unknown. Base d on the IEA 2008 report described in 
Section 3.2.9, it is unclear when the software was last updated. A search on the 
 38 
Fraunhofer ISE website for terms Hybrid and Dymola give references to work being done 
at:  
http://www.ise.fraunhofer.de/welcome-to-the-web-pages-of-the-fraunhofer-institute-for-
solar-energy-systems?set_language=en&cl=en 
References 
• See link for Matthias Vetter, Fraunhofer ISE for a description of the HySys tool:   
http://www.iea-pvps-task11.org/id39.htm 
• Modelica is an object-oriented modeling language and can be found at: 
http://www.modelica.org/  
• The Dymola software, which uses the Modelica modeling language is from 
Dynasim AB in Sweden and can be found at: http://www.dynasim.se/dymola.htm   
4. Battery Performance Models 
Photovoltaic systems provide varying amounts of power throughout the day due to the 
intermittent nature of sunlight reaching PV panels. Cloudy days, varying temperatures, 
system latitude, module configuration and shading effects directly affect the amount and 
timing of photovoltaic energy that can be produced.  
 
To help smooth out the variability in power production and satisfy system loads, batteries 
are used to store excess energy and use it wh en system loads are greater than PV output. 
Batteries used in PV systems are subject to different stresses as compared to traditional 
battery applications due to shallow charge -discharge cycling, among other things. 
Initially, automobile and boat lead -acid batteries were used for energy storage, however 
due to the unique demands imposed by PV generated electricity, manufacturers are 
developing batteries specifically for use in PV systems. Battery chemistries besides lead -
acid are undergoing research and in some cases currently being used to store energy from 
distributed sources like PV and wind (Kivya and Ostergaard 2009). 
 
To better understand how batteries store and release electricity, models were developed 
based on a variety of methodologies and can be generally grouped into the following: 1) 
performance-based lifetime or physico -chemical 2) cycle counting or weighted Ah 
throughput and 3) event-oriented (Sauer and Wenzl, 2008; Wenzl et al. 2005).  
 
Recently the European Union (EU) led an international benchmarking project for hybrid 
power systems in 2005 to better understand battery model limitations and potential fixes 
(Bindner et al., 2005). Also, work by Sauer and Wenzl (2008) identifies the need for 
better modeling techniques  and other models that can simulate performance on 
chemistries other than lead -acid. In addition, newer battery technologies are being 
introduced for hybrid and electric vehicles (EV’s), which may eventually be appropriate 
for PV systems when these technologies are better understood, are tested in PV and 
hybrid systems, and costs decrease. 
 39 
 
Most of the battery models discussed in this section are implemented in the hybrid system 
models described in Section 3, as these models are well known and have undergone 
extensive testing and validation. This discussion on battery storage models will first look 
at what SNL has done in terms of modeling energy storage for PV systems, and then go 
into battery models used by other researchers. 
4.1 Battery Performance Models Developed and Used by Sandia 
National Laboratories 
4.1.1 SIZEPV 
Description 
SIZEPV was developed by Chapman (1987) the author of Hy sim described in Section 
3.1.3. The purpose of SIZEPV was to determine the optimal configuration of a PV 
system with battery storage using a loss -of-load probabi lity model. The results of this 
model were by comparing with loss -of-load probabilities calculated with PVForm. The 
advantage of using SIZEPV for PV systems with battery storage is the ability to run 
multiple iterations much quicker than if set up using PVForm. 
The model is limited to lead-acid batteries. Required input data includes  battery capacity, 
minimum allowable state -of-charge (SOC), equalization SOC, backup capacity, 
equalization schedule, beginning SOC, maximum charge efficiency and maximum 
discharge efficiency.  
Availability and Maintenance 
The equations for SIZEPV are presented in the report by Chapman (1987). The program 
is not currently available for use. 
References 
• Chapman, R. N., 1987, Sizing Handbook for Stand-Alone Photovoltaic/Storage 
Systems, 
SAND87-1087. Sandia National Laboratories, Albuquerque, NM, April 
1987. 
• Menicucci, D. F., and J. P. Fernandez, 1988, User’s Manual for PVFORM: A 
Photovoltaic System Simulation Program for stand-alone and grid-interactive 
applications, SAND85-0376. Sandia National Laboratories, Albuquerque, NM, 
April 1988. 
4.1.2 Artificial Neural Network Technique 
Description 
Urbina et al. (1998) developed a probabilistic model for determining battery behavior 
when connected to a PV system. This technique uses an artificial neural network (ANN) 
to look at the probabilistic nature of battery operation. Input data for solar radiation is 
modeled using either a bivariate, first order Markov chain or canonical variate analysis 
 40 
(CVA). The resulting modeling for the PV -battery system is performed using a Monte 
Carlo analysis.  
This type of modeling is considered inductive or non- phenomenological bec ause the 
inputs and outputs are statistically derived through training behavior rather than the more 
traditional observed mathematically derived process.  S NL has performed this type of 
inductive modeling with lead-acid as well as lithium-ion batteries. 
Availability and Maintenance 
The equations are described in papers by Urbina et al. (1998) and Urbina et al. (2000). 
References 
• Urbina, A., R. Jungst, D. Ingersoll, T. Paez, G. O’Gorman, and P. Barney, 1998, 
Probabilistic Analysis of Rechargeable Batteries in a Photovoltaic Power Supply 
System, 194th Electrochemical Society Meeting, Boston, MA, November 1-6, 
1998. [SAND98-2635C]  
• Urbina, A., T. Paez and R. Jungst, 2000, Stochastic Modeling of Rechargeable 
Battery Life in a Photovoltaic Power System, 35th Intersociety Energy Conversion 
Engineering Conference, AIAA-2000-2976, Las Vegas, NV, July 24-28, 2000. 
[SAND2000-1541C] 
4.2 Other Battery Performance Models 
4.2.1 KiBaM 
Description 
The Kinetic Battery Model (KiBaM) is a lead -acid battery modeling application 
developed by Manwell and McGowan (1993) at the University of Massachusetts RERL. 
The charging analysis portion of the model is ba sed on the dissertation by Facinelli 
(1983) and the discharge analysis is based on the BEST model by Hyman (1986). KiBaM 
is considered a phenomenological model where many of the battery parameters are 
derived from extensive testing, and uses a modified amp- hour (Ah) cycle counting 
method to model battery performance and lifetime. The original version was built for 
wind/diesel systems with PV added in later versions. HOMER , as discussed above in 
Section 3.2.1 uses a simplified version of the KiBaM model. 
The Hybrid2 software program ( Section 3.2.2)  uses KiBaM for modeling battery 
performance. A recent benchmarking program undertaken by the EU (Bindner et al., 
2005) led to improvements in the model. The model available for download is the revised 
version of Ki BaM which incorporates recommendations made by the benchmarking 
project. Some of these improvements include better tracking of cycle charge and 
discharge rates, and expansion of the lifetime model to look at both cycle means and 
ranges (Bindner et al., 2005). 
 41 
Availability and Maintenance 
The program is available from RERL at: 
http://www.ceere.org/rerl/projects/software/batteryModel.html  
A theory manual is also available for Hybrid2 and describes the algorithm used by 
KiBaM: http://www.ceere.org/rerl/projects/software/hybrid2/Hy2_theory_manual.pdf  
The improvements to KiBaM based on the benchmarking activities is available at: 
http://www.ceere.org/rerl/publications/published/2005/AWEA05BatteryModel.pdf    
References 
• Facinelli, W. A., 1983, Modeling and Simulation of Lead-Acid Batteries for 
Photovoltaic Systems, Ph.D. dissertation, Arizona State University, Tempe, AZ. 
• Hyman, E., 1986, Modeling and Computerized Characterization of Lead-Acid 
Battery Discharges, BEST Facility Topical Report RD 83-1, NTIS Report 
DOE/ET/29368-T13. 
• Manwell, J. F. and J. G. McGowan, 1993, Lead Acid Battery Storage Model for 
Hybrid Energy Systems, Solar Energy, Vol. 50, No. 5, pp. 399-405. 
• Bindner, H., T. Cronin, P. Lundsager, J. Manwell, U. Abdulwahid, I. Baring-
Gould, 2005,  Lifetime Modelling of Lead Acid Batteries, Riso-R-1515. Riso 
National Laboratory, Roskilde, Denmark, April 2005. 
• Other references to KiBaM can be found at: 
http://www.ceere.org/rerl/rerl_publications.html 
4.2.2 FhG/Riso 
Description 
The FhG/Riso model utilizes an equivalent circuit battery performance (weighted -Ah) 
and lifetime model developed by Puls (1997) and is derived from PV system modeling by 
Fraunhofer-Gesellschaft (FhG). The voltage equation in the Puls model is based off of 
early work by Shepherd (1965). A detailed description of model assumptions and 
equations is given by Bindner et al. (2005) as part of the EU benchmarking project. 
Recommendations for model improvement as identified in the benchmarking project 
included the addition of additional testing data, creating a validation model, 
implementation of more stress factors and damage mechanisms, and incorporating other 
tests for input data.  The group at Riso National Laboratory mentions including this 
battery model into IPSYS (Section 3.2.8) (Bindner et al. 2005). 
Availability and Maintenance 
Model equations are presented in detail in the Benchmarking report by Bindner et al. 
(2005). Detailed equations can be found in the thesis by Puls (1997). 
 42 
References 
• Shepherd, C. M., 1965, Design of Primary and Secondary Cells, II. An Equation 
Describing Battery Discharge, J. Electrochem. Soc., Vol. 112, pp 657-664. 
• Puls, H. G., 1997, Evolutionsstrategien zur Optimierung autonomer Photovoltaik-
Systeme, diploma thesis, Albert-Ludwigs University, Freiburg, Germany. 
• Bindner, H., T. Cronin, P. Lundsager, J. Manwell, U. Abdulwahid, I. Baring-
Gould, 2005,  Lifetime Modelling of Lead Acid Batteries, Riso-R-1515. Riso 
National Laboratory, Roskilde, Denmark, April 2005. 
• Baring-Gould, I., H. Wenzl, R. Kaiser, N. Wilmot, F. Mattera, S. Tselepis, F. 
Nieuwenhout, C. Rodrigues, A. Perujo, A. Ruddell, P. Lundsager, H. Bindner, T. 
Cronin, V. Svoboda, and J. Manwell, 2005, Detailed Evaluation of Renewable 
Energy Power System Operation: A Summary of the European Union Hybrid 
Power System Component Benchmarking Project, Preprint, NREL/CP-500-
38209. National Renewable Energy Laboratory, Golden, CO, May 2005. 
4.2.3 CIEMAT  
Description 
The Centro de Investigaciones Energeticas, Medioambientales y Technologicas 
(CIEMAT) in Spain has a battery storage model based on work by Copetti et al. (1993), 
and partially based on work by Shepherd (1965). The model was built to predict charge 
and discharge for  lead-acid batteries produced by many different manufacturers rather 
than the more costly and time consuming effort of developing parameters for each brand 
of battery (Copetti et al., 1993; Achaibou et al., 2009). The application of this model to a 
hybrid PV/wind system is described by Gergaud et al. (2003), and is likely the battery 
model used in HySys (Section 3.2.9), although not confirmed.  
Availability and Maintenance 
Equations used by the CIEMAT model are available in the reference section. 
References 
• Shepherd, C. M., 1965, Design of Primary and Secondary Cells, II. An Equation 
Describing Battery Discharge, J. Electrochem. Soc., Vol. 112, pp 657-664. 
• Copetti, J. B., E. Lorenzo, and F. Chenlo, 1993, A General Battery Model for PV 
System Simulation, Progress in Photovoltaics, Vol. 1, pp 283-292. 
• Gergaud, O. G. Robin, B. Multon, and H. B. Ahmed, 2003, Energy Modeling of a 
Lead-Acid Battery within Hybrid Wind / Photovoltaic Systems, 10
th European 
Conference on Power Electronics and Applications, Toulouse, France, September 
2-4, 2003.  Available at: http://www.bretagne.ens-
cachan.fr/pdf/mecatronique/EnergiesRenouv/LeadAcidBattery_Gergaud_EPE200
3.pdf  
 43 
• Achaibou, N., M. Haddadi, and A. Malek, 2008, Lead Acid Batteries Simulation 
Including Experimental validation, J. of Power Sources, Vol. 185, pp. 1484-1491. 
4.2.4 CEDRL 
Description 
The CEDRL model was developed for Natural Resource Canada’s CEDRL Photovoltaic 
and Hybrid Systems group by Ross (2001a, 2001b). This semi -empirical model is a 
modified version of work by Shepherd (1965) and by Copetti et al. (1993)  for the 
relationship between state of charge and current/voltage. The model is written for use 
within the Matlab Simulink environment. Equations for this model are used in HybSim, 
the hybrid system model developed at S NL (Section 3.1.2) and the PVToolbox program 
(Section 3.2.5).  
Availability and Maintenance 
Equations describing the battery model can be found in the references below, as well as 
the publications of the Renewable Energy Research (RER) consulting company webpage: 
http://www.rerinfo.ca/english/publications/all.html.  
References 
• Shepherd, C. M., 1965, Design of Primary and Secondary Cells, II. An Equation 
Describing Battery Discharge, J. Electrochem. Soc., Vol. 112, pp 657-664. 
• Copetti, J. B., E. Lorenzo, and F. Chenlo, 1993, A General Battery Model for PV 
System Simulation, Progress in Photovoltaics, Vol. 1, pp 283-292. 
• Ross, M. M. D., 2001a, A Lead-Acid Battery Model for Hybrid System Modelling, 
Report to CETC-Varennes (Natural Resources Canada), Montreal, Quebec. 
Available at: 
http://www.rerinfo.ca/english/publications/pubReport2001battmodel.html  
• Ross, M. M. D., 2001b, A Simple but Comprehensive Lead-Acid Battery Model 
for Hybrid System Simulation, Proceedings of PV Horizon: Workshop on 
Photovoltaic Hybrid Systems, Montreal, Quebec, September 10, 2001. 
http://www.rerinfo.ca/english/publications/pubPVHorizon2001battmodel.html  
5. PV Modeling Effort Improvements Underway at 
Sandia National Laboratories 
SNL is actively working to improve the accuracy and value of PV performance models 
by focusing on a number of related technical areas listed below. 
• Developing standardized techniques for PV performance model validation 
• Characterizing PV performance model uncertainty and sensitivity  
 44 
• Building models capable of simulating performance of large PV plants 
5.1 PV Model Validation 
Model validation is the process of evaluating the degree to which a performance model 
accurately represents the actual performance of a fielded PV system. S NL researchers are 
developing a standard validation process that compares measured performance data with 
the performance predicted by a model in order to better understand how to use and 
interpret model results. A standardized validation approach will allow different models to 
be compared with a set of quality controlled data from well instrumented fielded sys tems 
in a variety of climates. Model users can examine these validation results to evaluate the 
strengths and weaknesses of different models for different applications. Model 
developers can apply these standardized validation methods.  
SNL's standardized approach to model validation for PV performance models focuses on 
comparing measured and modeled data in a number of different ways that provide 
insights into the accuracy of the model under different conditions. Perhaps the most 
obvious comparison that is made is for the total amount of energy produced by the 
system over different time periods (e.g., annual and monthly). Other comparisons 
examine measured and modeled energy output under specific ranges of environmental 
conditions (e.g., temperature, irradia nce, winds speed, etc.). This comparison provides 
model developers with important information about how a particular model compares 
with other models, and under what specific set of conditions might result in poor model 
performance. One challenge with developing a meaningful comparison between 
measured and simulated data is that most quantitative comparisons assume there is no 
uncertainty in the data. Appropriate treatment of uncertainty both in measured and 
modeled data is an important aspect of model vali dation this is usually overlooked when 
models are validated.  S NL’s effort towards evaluating the sources and magnitudes of 
uncertainties in PV performance modeling is outlined in the next section. 
5.2 Model Uncertainty and Sensitivity 
PV performance models al l rely on some set of parameters that describe the ability of a 
given PV array or module to produce power under a given set of environmental and site 
conditions. These parameters are typically determined from tests run at known conditions 
in the laboratory  (e.g., standard testing conditions (STC)) or at outdoor testing 
laboratories where environmental conditions are measured with high accuracy (e.g., 
Sandia National Laboratories’ PV Systems Optimization Laboratory ). As with any test, 
there are uncertainties  related to the measurement and interpretation of data (e.g., 
regression analyses) that can propagate and contribute to uncertainties in the predicted 
output from a model. In addition, different models and modeling approaches exist for 
predicting PV perfor mance and therefore the choice and application of a model adds a 
degree of model uncertainty. S NL is currently working to apply standard methods of 
uncertainty analysis to evaluate parameter and model uncertainties associated with 
current practices for PV performance modeling.   
The approach being pursued by S NL is to employ stochastic methods (e.g. Monte Carlo 
analysis) to propagate parameter uncertainties in several of the available models 
 45 
discussed in this report. Current efforts are focused on evaluatin g uncertainty in the 
Sandia PV Array Performance Model and the other models included as part of the Solar 
Advisor Model (SAM) as well as for PVSYST. In addition to estimating uncertainty, 
these analyses will use methods such as stepwise regression to ident ify and rank the 
sensitivity of model results to each of the uncertain input parameters. Such results will 
help researchers and industry identify areas where increased accuracy of measurements 
would have the greatest positive impact on model accuracy.  
5.3 Modeling Large PV Plants 
All models included in this survey assume that the PV array is small enough such that a 
single irradiance value (along with co -located weather parameters) is representative of 
the conditions across the entire array for each time step in the calculation. As large, 
multi-megawatt PV plants begin to proliferate, the fact that irradiance patterns over these 
large arrays are not uniform in time and space becomes important. Updated modeling 
approaches are necessary in order to more accuratel y represent the performance of such 
systems. SNL is actively involved in deploying networks of irradiance sensors to evaluate 
the spatial and temporal patterns in irradiance at the sites of large PV arrays. The result of 
this research is aimed at developin g a model of PV performance that can represent, 
and/or use as input, spatially and temporally complex patterns of irradiance and still 
provide accurate estimates of aggregated PV plant performance. Such a model is needed 
to better understand the impact of integrating large PV plants into the existing 
distribution and transmission grids.  
6. Assertion of Copyright 
Some of the codes evaluated in this report were developed in the 1970’s and 1980’s, prior 
to the processes now in place that require S NL to assert copyright of these codes with the 
Department of Energy before releasing or licensing them to the public.  For S NL 
employees, complete instructions for the assertion of copyright can be found on the 
internal (restricted) SNL network, at: 
Internal: 
http://www.irn.sandia.gov/legal/intellectual/copyright.html   
Information regarding licensing intellectual property (including software and codes) from 
SNL can be found at the following external website: 
External: 
http://ipal.sandia.gov/  
 
 
 46 
References 
Achaibou, N., M. Haddadi, and A. Malek, 2008, Lead Acid Batteries Simulation 
Including Experimental validation, J. of Power Sources, Vol. 185, pp. 1484-1491. 
Aronson, E. A., D. L. Caskey and B. C. Caskey, 1981, SOLSTOR Description and User’s 
Guide, SAND79-2330. Sandia National Laboratories, Albuquerque, NM, March 1981. 
Aronson, E. A., D. L. Caskey and K. D. Murphy, 1982, SOLSTOR II Description and 
User’s Guide, SAND82-0188. Sandia National Laboratories, Albuquerque, NM, June 
1982. 
Baring-Gould, I., H. Wenzl, R. Kaiser, N. Wilmot, F. Mattera, S. Tselepis, F. 
Nieuwenhout, C. Rodrigues, A. Perujo, A. Ruddell, P. Lundsager, H. Bindner, T. Cronin, 
V. Svoboda, and J. Manwell, 2005, Detailed Evaluation of Renewable Energy Power 
System Operation: A Summary of the European Union Hybrid Power System Component 
Benchmarking Project, Preprint, 
NREL/CP-500-38209. National Renewable Energy 
Laboratory, Golden, CO, May 2005. 
Bindner, H., T. Cronin, P. Lundsager, J. Manwell, U. Abdulwahid, I. Baring-Gould, 
2005,  Lifetime Modelling of Lead Acid Batteries, Riso-R-1515. Riso National 
Laboratory, Roskilde, Denmark, April 2005. 
Braun, J. E., and J. C. Mitchell, 1983, Solar Geometry for Fixed and Tracking Surfaces, 
Solar Energy, Vol. 31, No.5, pp. 439-444. 
Bugler, J. W., 1977, The Determination of Hourly Insolation on an Inclined Plane using 
a Diffuse Irradiance Model Based on Hourly Measured Global Horizontal Insolation, 
Solar Energy, Vol. 19, No. 5, pp. 477-491. 
Cameron, C. P., W. E. Boyson, D. M. Riley, 2008, Comparison of PV System 
Performance-Model Predictions with Measured PV System Performance. 33
rd IEEE 
PVSC, San Diego, CA, May 12-16, 2008. Available at: 
https://www.nrel.gov/analysis/sam/pdfs/2008_sandia_ieee_pvsc.pdf  
Caskey, D. L, E. A. Aronson, and K. D. Murphy, 1981, Parametric Analysis of Stand-
Alone Residential Photovoltaic Systems and the SOLSTOR Simulation Model, 15
th IEEE 
PVSC, Kissimmee, FL, May 12-15, 1981. [SAND81-1130C] 
Chamberlin, J. L., 1988, Performance Modeling of Lead-Acid batteries in Photovoltaic 
Applications, 20th IEEE PVSC, Las Vegas, NV, September 26-30, 1988. [SAND88-
0594C] 
Chapman, R. N., 1987, Sizing Handbook for Stand-Alone Photovoltaic/Storage Systems, 
SAND87-1087. Sandia National Laboratories, Albuquerque, NM, April 1987. 
 47 
Chapman, R. N., 1996, Hybrid Power Technology for Remote Military Facilities, 
Powersystems World ’96, Las Vegas, NV, September 7-13, 1996. [SAND96-1867C]  
Clark, D. R., S. A. Klein, W. A. Beckman, 1984, A Method for Estimating the 
Performance of Photovoltaic Systems, Solar Energy, Vol. 33, No. 6, pp. 551-555. 
Copetti, J. B., E. Lorenzo, and F. Chenlo, 1993, A General Battery Model for PV System 
Simulation, Progress in Photovoltaics, Vol. 1, pp 283-292. 
Davies, J. A., and J. E. Hay, 1980, Calculation of the Solar Radiation Incident on an 
Inclined Surface in Proc. First Canadian Solar Radiation Data Workshop (J. E. Hay and 
T. K. Won, eds.), pp. 32-58, April 17-19, 1978. 
DeSoto, W., 2004, Improvement and Validation of a Model for Photovoltaic Array 
performance, M.S. thesis, University of Wisconsin-Madison, Madison, WI. Available at: 
http://sel.me.wisc.edu/theses/desoto04.zip 
DeSoto, W., S. A. Klein, and W. A. Beckman, 2006, Improvement and Validation of a 
Model for Photovoltaic Array performance, Solar Energy, Vol. 80, No. 1, pp. 71-80. 
Divya, K. D., and J. Ostergaard, 2009, Battery Energy Storage Technology for Power 
Systems – An Overview, Electric Power Systems Research, Vol. 79, No. 4, pp. 511-520. 
Duffie, J. A. and W. A. Beckman, 1991, Solar Engineering of Thermal Processes. 
Second Edition, John Wiley & Sons, Inc., New York, NY. 
Eckstein, J. H., 1990, Detailed Modeling of Photovoltaic System Components, M.S. 
thesis, University of Wisconsin-Madison, Madison, WI. Available at: 
http://sel.me.wisc.edu/theses/eckstein90.zip  
Evans, D. L., W. A. Facinelli and R. T. Otterbein, 1978, Combined Photovoltaic/Thermal 
System Studies, SAND78-7031. Sandia National Laboratories, Albuquerque, NM, August 
1978. 
Evans, D. L., W. A. Facinelli, and L. P. Koehler, 1980, Simulation and Simplified Design 
Studies of Photovoltaic Systems, SAND80-7013. Sandia National Laboratories, 
Albuquerque, NM, September 1980. 
Evans, D. L., W. A. Facinelli, and L. P. Koehler, 1981, Simplified Design Guide for 
Estimating Photovoltaic Flat Array and System Performance, SAND80-7185. Sandia 
National Laboratories, Albuquerque, NM, March 1981. 
Evans, D. L., 1981, Simplified Method for Prediction Photovoltaic Array Output, Solar 
Energy, Vol. 27, No. 6, pp. 555-560. 
Facinelli, W. A., 1983, Modeling and Simulation of Lead-Acid Batteries for Photovoltaic 
Systems, Ph.D. dissertation, Arizona State University, Tempe, AZ. 
 48 
Fanney, A. H., B. P. Dougherty, and M. W. Davis, 2002, Evaluating Building Integrated 
Photovoltaic Performance Models, 29th IEEE Photovoltaic Specialists Conference, New 
Orleans, LA, May 17 and 24 2002. 
Fanney, A. H., M. W. Davis, B. P. Dougherty, D. L. King, W. E. Boyson, and J. A. 
Kratochvil, 2006, Comparison of Photovoltaic Module Performance Measurements, J. of 
Solar Energy Engineering, Vol. 128, No. 2, pp. 152-159. 
Fanney, A. H., B. P. Dougherty, and M. W. Davis, 2009, Comparison of Predicted to 
Measured Photovoltaic Module Performance, Solar Energy Engineering, Vol. 131, No. 2, 
10p.  
Fuentes, M. K., 1987, A Simplified Thermal Model for Flat-Plate Photovoltaic Arrays, 
SAND85-0330. Sandia National Laboratories, Albuquerque, NM, May 1987. 
Gergaud, O. G. Robin, B. Multon, and H. B. Ahmed, 2003, Energy Modeling of a Lead-
Acid Battery within Hybrid Wind / Photovoltaic Systems, 10th European Conference on 
Power Electronics and Applications, Toulouse, France, September 2-4, 2003.  Available 
at: http://www.bretagne.ens-
cachan.fr/pdf/mecatronique/EnergiesRenouv/LeadAcidBattery_Gergaud_EPE2003.pdf  
Gilman, P., N. Blair, M. Mehos, C. Christensen, S. Janzou, and C. Cameron, 2008, Solar 
Advisor Model User Guide for Version 2.0, 
NREL/TP-670-43704. National Renewable 
Energy Laboratory, Golden, CO, August 2008. 
Goldstein, L. H, and G. R. Case, 1977, PVSS – A Photovoltaic System Simulation 
Program Users Manual, SAND77-0814. Sandia National Laboratories, Albuquerque, 
NM, June 1977. 
Goldstein, L. H., and G. R. Case, 1978, PVSS – A Photovoltaic System Simulation 
Program, Solar Energy, Vol. 23, No. 1, pp.37-43. 
Gueymard, C., 1987, An Anisotropic Solar Irradiance Model for Tilted Surfaces and its 
Comparison with Selected Engineering Algorithms, Solar Energy, Vol. 38, No. 5, pp. 
367-386. Erratum, Solar Energy, 1988, Vol. 40, No.2, p. 175. 
Hay, J. E., 1979, Calculating of Monthly Mean Solar Radiation for Horizontal and 
Inclined Surfaces, Solar Energy, Vol. 23, pp. 301-307. 
Hoover, E. R., 1980, SOLCEL-II An Improved Photovoltaic System Analysis Program, 
SAND79-1785. Sandia National Laboratories, Albuquerque, NM, February 1980. 
Hyman, E., 1986, Modeling and Computerized Characterization of Lead-Acid Battery 
Discharges, BEST Facility Topical Report RD 83-1, NTIS Report DOE/ET/29368-T13. 
Jakobides, F., 2001, Nutzung empirischer Datensätze zur Bestimmung der 
Modellparameter für Solarzellen auf der Basis von kristallinem und amorphen Silizium, 
 49 
M.S. thesis, Fachhochschule Magdeburg, Germany. Available at: 
http://www.insel.eu/fileadmin/insel.eu/diverseDokumente/Diplomarbeit_Fr.Jabobides.pdf   
Jones, G. J., and R. N. Chapman, 1987, Photovoltaic/Diesel Hybrid Systems: The Design 
Process, 19th IEEE PVSC, New Orleans, LA, May 4-8, 1987. [SAND87-1203C] 
Jennings, S. U., 1996, Development and Application of a Computerised Design Tool for 
Remote Area Power Supply Systems. PhD dissertation, Murdoch University, Perth, 
Australia. 
Kendrick, L., J. Pihl, I. Weinstock, D. Meiners, and D. Trujillo, 2003, Hybrid Generation 
Model Simulator (HYBSIM), EESAT Conference, San Francisco, CA, October 27-29, 
2003. [
SAND2003-3790A] 
King, D. L., J. K. Dudley, and W. E. Boyson, 1996, PVSIM: A Simulation Program for 
Photovoltaic Cells, Modules, and Arrays, 25
th IEEE PVSC, Washington, DC, May 13-17, 
1996. [SAND95-2673C]  
King, D. L., W. E. Boyson and J. A. Kratochvil, 2004, Photovoltaic Array Performance 
Model, SAND2004-3535. Sandia National Laboratories, Albuquerque, NM, August, 
2004. 
King, D. L., S. Gonzalez, G. M. Galbraith, and W. E. Boyson, 2007, Performance Model 
for Grid-Connected Photovoltaic Inverters, SAND2007-5036. Sandia National 
Laboratories, Albuquerque, NM, September 2007. 
Klucher, T. M., 1978, Evaluation of Models to Predict Insolation on Tilted Surfaces, 
NASA TM-78842, NASA, Lewis Research Center, Cleveland, OH, March, 1978. 
Lewis, C. A., and J. P. Kirkpatrick, 1970, Solar Cell Characteristics at High Solar 
Intensities and Temperatures, 8th IEEE PVSC, Seattle, WA, August 4-6, 1970. 
Linn, J. K., 1977, Photovoltaic System Analysis Program – SOLCEL, SAND77-1268. 
Sandia National Laboratories, Albuquerque, NM, August 1977. 
Liu, B. Y. H, and R. C. Jordan, 1963, The Long-Term Average Performance of Flat-Plate 
Solar Energy Collectors, Solar Energy, Vol. 7, No. 2, pp. 53-74. 
Manwell, J. F. and J. G. McGowan, 1993, Lead Acid Battery Storage Model for Hybrid 
Energy Systems, Solar Energy, Vol. 50, No. 5, pp. 399-405. 
Marion, B., M. Anderberg, P. Gray-Hann, and D. Heimiller, 2001, PVWATTS Version 2 – 
Enhanced Spatial Resolution for Calculating Grid-Connected PV Performance: Preprint, 
NREL/CP-560-30941. National Renewable Energy Laboratory, Golden, CO, October 
2001. 
 50 
Marion, B., M. Anderberg, and P. Gray-Hann, 2005, Recent and Planned Enhancements 
for PVWATTS, NREL/CP-520-38975. National Renewable Energy Laboratory, Golden, 
CO, November 2005. 
Mehos, M., and D. Mooney, 2005, Performance and Cost Model for Solar Energy 
Technologies in Support of the Systems-Driven Approach, NREL/CP-550-37085. 
National Renewable Energy Laboratory, Golden, CO, January 2005. 
Menicucci, D. F., 1985, PVFORM – A New Approach to Photovoltaic System 
Performance Modeling, 18th IEEE PVSC, Las Vegas, NV, October 21-25, 1985. 
Menicucci, D. F., 1986, Photovoltaic Array Performance Simulation Models, Solar Cells, 
Vol. 18, pp. 383-392. 
Menicucci, D. F., and J. P. Fernandez, 1988, User’s Manual for PVFORM: A 
Photovoltaic System Simulation Program for stand-alone and grid-interactive 
applications, SAND85-0376. Sandia National Laboratories, Albuquerque, NM, April 
1988. 
Mermoud, A., 1995, Use and Validation of PVSYST, A User-Friendly Software for PV-
system Design, 13th European Photovoltaic Solar Energy Conference, Nice, France, 
October 23-27, 1995. 
Newmiller, J., C. Whitaker, M. Ropp, B. Norris, 2008, Renewable Systems 
Interconnection Study: Distributed Photovoltaic Systems Design and Technology 
Requirements, SAND2008-0946P. Sandia National Laboratories, Albuquerque, NM, 
February 2008. 
Obst, C., 1994, Kennlinienmessung an Installierten Photovoltaik-Generatoren und deren 
Bewertung, M.S. thesis, University of Oldenburg, Germany. 
Ortmeyer, T., R. Dugan, D. Crudele, T. Key, and P. Barker, Renewable Systems 
Interconnection Study: Utility Models, Analysis, and Simulation Tools, 
SAND2008-
0945P. Sandia National Laboratories, Albuquerque, NM, February 2008. 
Patel, M. S., and T. L. Pryor, 2001, Monitored Performance Data from a Hybrid RAPS 
System and the Determination of Control Set Points for Simulation Studies, ISES 2001 
Solar World Congress, Adelaide, Australia, November 25-December 2, 2001.  
Perez, R., R. Stewart, C. Arbogast, R. Seals and D. Menicucci, 1987, A New Simplified 
Version of the Perez Diffuse Irradiance Model for Tilted Surfaces, Solar Energy, Vol. 39, 
pp. 221-231. 
Perez, R., R. Stewart, R. Seals, T. Guertin, 1988, The Development and Verification of 
the Perez Diffuse Radiation Model, 
SAND88-7030. Sandia National Laboratories, 
Albuquerque, NM, October 1988. 
 51 
Puls, H. G., 1997, Evolutionsstrategien zur Optimierung autonomer Photovoltaik-
Systeme, diploma thesis, Albert-Ludwigs University, Freiburg, Germany. 
Reindl, D. T., 1988, Estimating Diffuse Radiation on Horizontal Surfaces and Total 
Radiation on Tilted Surfaces, M.S. thesis, University of Wisconsin-Madison, Madison, 
WI. 
Ross, M. M. D., 2001a, A Lead-Acid Battery Model for Hybrid System Modelling. Report 
to CETC-Varennes (Natural Resources Canada), Montreal, Quebec. Available at: 
http://www.rerinfo.ca/english/publications/pubReport2001battmodel.html  
Ross, M. M. D., 2001b, A Simple but Comprehensive Lead-Acid Battery Model for 
Hybrid System Simulation, Proceedings of PV Horizon: Workshop on Photovoltaic 
Hybrid Systems, Montreal, Quebec, September 10, 2001. 
http://www.rerinfo.ca/english/publications/pubPVHorizon2001battmodel.html  
Ross, M. M. D, 2003, Validation of the PVToolbox Against the First Run of the Battery 
Capacity Cycling Test, Report to CETC-Varennes (Natural Resources Canada), Montreal, 
Quebec. Available at: 
http://www.rerinfo.ca/english/publications/pubReport2003PVTboxValidBCap.html 
Sauer, D., and H. Wenzl, 2008, Comparison of Different Approaches for Lifetime 
Prediction of Electrochemical Systems – Using Lead-Acid Batteries as Example, J. of 
Power Sources, Vol. 176, No. 2, pp. 534-546. 
Shepherd, C. M., 1965, Design of Primary and Secondary Cells, II. An Equation 
Describing Battery Discharge, J. Electrochem. Soc., Vol. 112, pp. 657-664. 
Siegel, M. D., S. A. Klein, and W. A. Beckman, 1981, A Simplified Method for 
Estimating the Monthly-Average Performance of Photovoltaic Systems, Solar Energy, 
Vol. 26, No. 5, pp. 413-418. 
Skartviet, A., and J. A. Olseth, 1986, Modelling Slope Irradiance at High Latitudes, Solar 
Energy, Vol. 36, No. 4, pp. 333-344. 
Solar Energy Research Institute (SERI), 1985, Solar Energy Computer Models Directory, 
SERI/SP-271-2589. Solar Energy Research Institute, Golden, CO, August 1985. 
Temps, R. C., and K. L. Coulson, 1977, Solar Radiation Incident Upon Slopes of 
Different Orientation, Solar Energy, Vol. 19, No. 2, pp. 179-184. 
Thevenard, D., and M. M. D. Ross, 2002, Validation and Verification of Component 
Models and System Models for the PV Toolbox, Report to CETC-Varennes (Natural 
Resources Canada), Varennes, Quebec. Available at: 
http://www.rerinfo.ca/english/publications/pubReport2002PVToolboxValid.html  
 52 
Townsend, T. U., 1989, A Method for Estimating the Long-Term Performance of Direct-
Coupled Photovoltaic Systems, M.S. thesis, University of Wisconsin-Madison, Madison, 
WI. Available at: http://sel.me.wisc.edu/theses/townsend89.zip  
Urbina, A., R. Jungst, D. Ingersoll, T. Paez, G. O’Gorman, and P. Barney, 1998, 
Probabilistic Analysis of Rechargeable Batteries in a Photovoltaic Power Supply System, 
194th Electrochemical Society Meeting, Boston, MA, November 1-6, 1998. [SAND98-
2635C]  
Urbina, A., T. Paez and R. Jungst, 2000, Stochastic Modeling of Rechargeable Battery 
Life in a Photovoltaic Power System, 35th Intersociety Energy Conversion Engineering 
Conference, AIAA-2000-2976, Las Vegas, NV, July 24-28, 2000. [SAND2000-1541C] 
Van der Borg, J. J. C. M., and M. J. Jansen, 2003, Energy Loss Due to Shading in a BIPV 
Application, 3rd World Conference on Photovoltaic Energy Conversion, Osaka, Japan, 
May 11-18, 2003. Available at: http://www.ecn.nl/docs/library/report/2003/rx03024.pdf  
Van Dijk, V., 1996, Hybrid Photovoltaic Solar Energy Systems, Design, Operation, 
Modelling and Optimization of the Utrecht PBB System, PhD dissertation, Utrecht 
University, The Netherlands. 
Wenzl, H., I, Baring-Gould, R. Kaiser, B. Liaw, P. Lundsager, J. Manwell, A. Ruddell, 
and V. Svoboda, 2005, Life Prediction of Batteries for Selecting the Technically most 
Suitable and Cost Effective Battery, J. of Power Sources, Vol. 144, No. 2, pp. 373-384. 
 
Wilmott, C. J., On the Climatic Optimization of the Tilt and Azimuth of Flat-Plate Solar 
Collectors, Solar Energy, Vol. 28, No. 3, pp. 205-216. 
 
 53 
APPENDIX A 
 
PV and Hybrid Model Table 
 
The following table shows the difference in capabilities of both PV and hybrid system 
models. Battery models are not included in this matrix. The order of the models follows 
the same order as the report. These categories allow for comparison between each model 
and include the following: Type of model, plane -of-array radiation model, array 
performance, modeled technologies, weather and insolation, economics/financing and 
model status. A key is provided at the end of the table to describe certain terms in more 
detail. It is exceedingly likely that information was not discovered, or not made available 
to the authors during the compilation of this report that would indicate an update, 
improvement or provide additional information about a specific model. Therefore, this 
compilation does not represent an exhaustive effort and should be considered a working 
draft as some models are constantly updated and changed, and new models are 
introduced. Contacting the organization that manages each model will provide the most 
up-to-date information.  
 54 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
PVSS component N/A 
One-diode equivalent 
circuit and simple 
temperature model. 
cSi unk N/A 
Developed around 1976-
1977. No longer used or 
maintained. 
SOLCEL system N/A 
One-diode equivalent 
circuit, simple 
temperature model, 
passive or active 
cooling. 
cSi, CPV SOLMET Basic cost and LCOE. 
Developed and used from 
the mid-1970s to the mid-
1980s. No longer used or 
maintained. 
Evans and 
Facinelli 
component 
Array tilt 
correction 
factor 
Power temperature 
coefficient model 
(efficiency, 
temperature, array tilt 
correction factor). 
cSi, CPV SOLMET N/A 
Developed in the late 1970s 
to early 1980s timeframe. No 
longer used or maintained. 
PVForm system Perez et al. 
Modified power 
temperature coefficient 
model (efficiency, 
temperature and POA). 
Different equation used 
for two low and high 
irradiance levels. 
Fuentes thermal model. 
cSi TMY Basic input and lifecycle 
cost, LCOE. 
Developed in 1985 with the 
last update made in 1988. No 
longer maintained. PVForm 
can still be licensed from 
SNL. 
PVSIM component N/A Two-diode equivalent 
circuit. 
All PV 
technologies N/A N/A Developed in 1996. No 
longer used or maintained. 
Sandia PV Array 
Performance 
Model 
component N/A 
Empirically derived 
coefficients for the 
following: I-V curve, 
module temperature 
(thermal model), angle 
of incidence, air mass, 
and effective 
irradiance.  
cSi. CPV, mj-CPV, 
TF (CdTe, CiS, 
aSi) 
TMY 2/3,  
METEONORM, 
custom 
locations. 
N/A 
Developed between 1991 
and 2004. Currently used 
and maintained at SNL with 
new modules being added to 
database. Used in SAM. 
PVDesignPro system HDKR, Perez 
et al. 
Sandia PV Array 
Performance Model. 
cSi, CPV, mj-CPV, 
TF (CdTe, CiS, 
aSi) 
TMY 2/3, 
METEONORM, 
custom 
locations. 
Financial analysis including 
lifecycle and energy costs. 
Developed in the late 1990s. 
Maintained by the developer 
with v6.0 released in 2004. 
 55 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
Solar Advisor 
Model 
system 
Isotropic 
Sky, Hay and 
Davies, 
Reindl, 
Perez et al.  
Sandia PV Array 
Performance Model, 5-
Paramater Array 
Performance Model, 
simple-efficiency 
model, PVWatts. 
cSi, CPV, HIT, TF 
(CdTe, CiS, aSi) 
TMY2, EPW 
(TMY3), 
METEONORM. 
Energy cost, financing 
options, depreciation, tax 
credits/incentives, cash 
flow, LCOE. Residential, 
commercial and utility 
financing. 
Developed around 2006. 
Maintained by NREL. Last 
update in 2009 with version 
2009.10.2. 
5-Parameter 
Array 
Performance 
Model 
component N/A 
Semi-empirical 5-
parameter one-diode 
model. 
CEC 
implementation:  
cSi, BiPV, 
Ribbon,  TF (aSi, 
CdTe)  
N/A N/A 
Code is currently being 
updated by Wisconsin SEL to 
add more parameters. Used 
in SAM. 
PVWatts system 
Uses 
PVForm 
(Perez et al.) 
Uses PVForm Equation.   cSi 
TMY 2 for US.  
For international 
sites, SWERA, 
CWEC, IWEC. 
Calculates electricity cost 
and energy value. 
Maintained by NREL. Last 
update in 2008. Used in 
SAM. 
PVSYST system Hay, Perez 
et al. 
One-diode equivalent 
circuit. Modified one-
diode for stabilized aSi, 
CiS and CdTe thin-film 
modules. Also, Incident 
angle modifier, and air 
mass correction. 
cSi, µc-Si, HIT, TF 
(CdTe, CiS, aSi) 
Meteonorm, 
Satellight, TMY 2, 
ISM-EMPA, 
Helioclim-1 and 
3, NASA-SSE, 
WRDC, PVGIS-
ESRA, RETScreen. 
System financing, feed-in 
tariffs, annual and used 
energy costs. 
Developed in the mid 1990s. 
Currently updated in 2009 
with version 5.05. 
PV F-Chart system Isotropic Sky 
Monthly average of 
Instantaneous array 
output (function of 
efficiency and cell 
temperature). Also see 
Evans and Facinelli 
above. 
cSi, CPV TMY2 Life-cycle costs, equipment 
costs and cash flow. 
Developed in 1985. Last 
update was in 2001. 
PVSol system Hay and 
Davies 
Based on irradiance and 
module voltage at STC 
and efficiency 
characteristic curve. 
Linear or dynamic 
temperature model. 
Incident angle modifier. 
cSi, µc-Si, 
Ribbon, HIT, TF 
(CdTe, CiS, aSi) 
MeteoSyn, 
Meteonorm, 
PVGIS, NASA SSE, 
SWERA, custom 
locations. 
Economic efficiency for cash 
value factor, capital value, 
amortization period and 
electricity production costs. 
Developed in 1998. Last 
update of Expert was in 2009 
with version 4.0. 
 56 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
Polysun system unk unk 
cSi, µc-Si, 
Ribbon, HIT, TF 
(CdTe, CiS, aSi) 
Meteotest, 
custom 
locations. 
Financing, O&M costs, 
incentives, energy prices, 
fuel cost savings, system 
value. 
Developed in 2007. Last 
update was in 2009 with 
version 5.2. 
INSEL system 
Isotropic 
Sky, Temps 
and 
Coulson, 
[Bugler, Hay 
and 
Kambezidis], 
Klucher, 
Hay, 
Willmott, 
Skartveit 
and Olseth, 
Gueymard, 
Perez et al., 
and Reindl 
et al. 
One and two-diode 
equivalent circuit 
model. Four incident 
angle modifier models. 
cSi, others 
unknown 
Worldwide 
InselWeather 
database. 
Installed system cost, O&M 
costs, NPV, electricity cost, 
feed-in tariffs. 
Developed in 1991. Pre-
release of version 8.0 was 
available in late 2009. 
SolarPro System Unk 
One-diode equivalent 
circuit. Simple 
temperature model. 
cSi, HIT, TF 
(CdTe, aSi) 
Worldwide – 
provided by 
Japan 
Meteorological 
Agency.  
System O&M costs. 
Developed in 1997. Current 
version at time of this report 
is 3.0. 
Clean Power 
Estimator (CPE) 
system 
Uses 
PVForm 
(Perez et al.) 
Uses PVForm Equation. cSi, others 
unknown 
TMY2, 
Proprietary 
satellite 
measurements. 
financing, tax credits, utility 
rates, payback, cash flow, 
O&M costs, depreciation. 
Software is current. Clean 
Power Research can 
customize the CPE for any 
location in the US and has 
been in operation since 
1998. 
 57 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
PVOptimize system 
Uses 
PVWatts 
(PVForm) 
Uses PVWatts (PVForm) 
Equation. 
cSi, CPV, Ribbon, 
TF (CdTe, aSi) PVWatts (TMY2) 
Generates reports for State 
of California specific 
incentives (Performance 
Based Incentives), utility 
interface cost and credits. 
7-day evaluation version 
1.0.46 available at the time 
of this report. 
OnGrid system 
Uses 
PVWatts 
(PVForm) 
Uses PVWatts (PVForm) 
Equation. 
cSi, Ribbon,  TF 
(aSi, CdTe)  Uses PVWatts 
Generates reports for State 
of California specific 
incentives (Performance 
Based Incentives), utility 
interface cost and credits. 
Also works with other 
states incentive systems. 
Looks at system costs, 
federal incentives, 
depreciation, cash flow, IRR, 
and O&M costs. 
This software was released in 
2005 and consistently 
updated with options for 
monthly or annual 
subscriptions. Version 3_4a 
is the version available at the 
time of this report. 
CPF Tools system 
Uses 
PVWatts 
(PVForm) 
Uses PVWatts (PVForm) 
Equation. 
CEC 
implementation: 
cSi, Ribbon,  TF 
(aSi, CdTe)  
NCDC USHCN 
Generates custom reports. 
Federal and state 
incentives, cash flow, IRR, 
financing, LCOE, lifecycle 
payback, system resale 
value. 
Software is current with a 
monthly subscription cost. A 
7-day trial is available. CPF 
started operations in 2007. 
Solar Estimate system 
Uses 
PVWatts 
(PVForm) 
Uses PVWatts (PVForm) 
Equation. 
cSi, others 
unknown PVWatts (TMY2) 
System cost, federal, state 
and local financial 
incentives, cash flow 
analysis, savings and benefit 
analysis. 
On-line application was 
released in 2000. Web-based 
software is currently 
updated at the time of this 
report. 
 58 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
SOLSTOR Hybrid 
system N/A See SOLCEL See SOLCEL See SOLCEL 
lifecycle costs including 
capital cost, O&M, and 
energy purchase cost. 
Depreciation, ITC, salvage 
value, financing. 
Software was developed and 
maintained between 1979 
and 1982. It is no longer 
updated or supported. 
HybSim Hybrid 
system unk unk cSi 
15 minute max 
insolation, 
temperature and 
wind speed. 
Lifecycle costs for system 
components, such as PV, 
generator and batteries. It 
can look at cost and 
performance differences 
between a diesel only 
system with one consisting 
of different renewable 
sources (PV, wind) 
combined with storage 
(battery) and backup 
generators. 
Version 3.3 available for 
license. Work is on-going (as 
of 2009) to add more hybrid 
system components. Version 
1 was released in 2005. 
Hysim Hybrid 
system 
Uses 
PVForm 
(Perez et al.) 
Uses PVForm Equation. cSi TMY 2 
LCOE, lifecycle cost, fuel 
cost, O&M cost, cost 
comparison between 
alternative configurations. 
Hysim was available for use 
in 1987 with some 
applications as late as 1996. 
It is no longer used or 
updated. 
HOMER Hybrid 
system HDKR 
Power calculated as a 
function of incident 
radiation, derating, 
rated array capacity 
and PV cell 
temperature. 
Uses some input 
data from 
module 
manufacturer 
and other 
available data. 
Scaled data in a 
text file. User can 
select locations 
in software, use 
TMY 2 data or 
input custom 
data. 
Inputs include annual real 
interest rate, project 
lifetime, system fixed 
capital costs and O&M costs 
and capacity shortage 
penalty. Main outputs 
include total Net Present 
Cost (NPC), and LCOE. 
HOMER was developed in 
1993, and is available as of 
2009 through HOMER 
Energy. Version 2.67 beta 
(April 2008) was the most 
recent version at the time of 
this report. 
 59 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
Hybrid2 Hybrid 
system HDKR 5-parameter array 
performance model. 
cSi, TF (CdTe, 
CiS, aSi) unk 
lifecycle cost, cash flow, 
NPV, payback, IRR, tax 
credits, tradeoffs between 
different hybrid 
configurations. 
This program was developed 
in 1994 as Hybrid1, and then 
updated to Hybrid2 in 1996. 
The most recent version at 
the time of this report is 1.3e 
(2004). 
UW-Hybrid 
(TRNSYS) 
Hybrid 
system 
Isotropic 
Sky, Hay and 
Davies, 
Reindl, 
Perez et al. 
5-parameter array 
performance model (4-
parameter for 
crystalline, 5-parameter 
for TF). 
cSi, CPV, TF 
(CdTe, CiS, aSi) 
TMY, TMY 2, 
Meteonorm, 
EnergyPlus, 
IWEC. 
lifecycle cost analysis 
including cash flow, savings, 
payback period, rate of 
return. User can input state 
and federal tax incentives. 
TRNSYS was developed in 
1975 and continues to be 
utilized and updated for a 
variety of energy analysis 
capabilities. The most recent 
version at the time of this 
report is version 17. 
PVToolbox Hybrid 
system unk One-diode equivalent 
circuit. cSi, TF (aSi) unk O&M calculator for lifecycle 
cost analysis. 
It appears that the 
PVToolbox was initially 
created in the early 2000s for 
research in Canadian 
climates. The last updates to 
the model appear to have 
been made in 2007. 
RAPSIM Hybrid 
system unk unk cSi assumed, 
others unknown unk unk 
This software was developed 
in 1996 for use in Australia. 
Version 2.0 was available in 
1997. It is unknown if 
updates were made past 
1997. 
SOMES Hybrid 
system unk unk cSi assumed, 
others unknown unk unk 
SOMES was developed in 
1987, with version 3.0 
available in 1993, and 
version 3.2 available in 1997. 
It is unknown if updates 
were made past 1997. 
 60 
 Type of 
Model 
POA 
Radiation 
Model 
Array 
Performance 
Modeled PV 
Technologies 
Weather and 
Insolation Economics/Financing Model Status 
IPSYS Hybrid 
system unk unk cSi assumed, 
others unknown. unk unk 
Development for IPSYS 
appears to have started in 
2000, with a more formal 
discussion of the software in 
2004. It is unknown if 
updates were made past 
2004. 
HySys Hybrid 
system unk unk cSi assumed, 
others unknown. unk unk 
HySys version 1.0 was 
developed in 2003. Further 
research is identified by the 
IEA PVPS Task 11 in 2008. It 
is unknown if updates are 
available past the 2003 
version. 
Dymola/Modelica Hybrid 
system unk unk cSi assumed, 
others unknown. unk Lifecycle costs, LCOE. 
2008 is the last known date 
of the software from an IEA 
PVPS conference. 
 
 
Key for PV and Hybrid Model Table:   
unk - unknown 
N/A - not applicable 
Component - models individual or all components in a PV system such as array, inverter, charge controllers, batteries and system load.  
System - models all components of a PV or hybrid system and includes economic and financial analysis capabilities. May also include ba ttery 
storage. 
ISM - EMPA - Switzerland meteorological data. 
PVGIS ESRA - GIS interpolated meteorological layer for Europe and Africa. 
Helioclim - Europe and Africa Meteostat meteorological data. 
RETScreen - Worldwide meteorological dataset uses best location from 20 sources.  
Meteonorm - Worldwide meteorological dataset. 
Satellight - European meteorological dataset. 
MeteoSyn - Worldwide meteorological dataset. 
PVGIS - EU spatially enabled geobrowser for European and African meteorological data.  
Meteotest - Worldwide meteorological dataset. 
 
 
 61 
Distribution 
 
 
All Electronic Copies: 
Sandia National Laboratories 
 
1  0735 G. T. Klise, 6733 
1  1033 J. S. Stein, 6335 
1 0406 R. N. Chapman, 5713 
1  0613 R. G. Jungst, 2548 
1  0614 T. D. Hund, 2547 
1  0614 D. Ingersoll, 2546 
1  0734 W. I. Bower, 6338 
1  0734 V. P. Gupta, 6338 
1  0734 J. S. Nelson, 6338 
1  0734 E. B. Stechel, 6339 
1  0781 R. E. Fate, 6473 
1  0836 T. L. Aselage, 1514 
1  0982 M. Brown, 5737 
1  1006 D. J. Trujillo, 6441 
1  1033 C. J. Hanley, 6335 
1  1033 C. P. Cameron, 6335 
1  1033 D. Riley, 6335 
1  1033 M. A. Quintana, 6335 
1  1033 J. E. Granata, 6335 
1  1033 S. Gonzalez, 6335 
1  1033 A. Ellis, 6335 
1  1033 S. S. Kuszmaul, 6335 
1  1033 L. Pratt, 6335 
1  1033 B.L. Schenkman, 6336  
1  1108 J. J. Torres, 6332 
1  1108 J. D. Boyes, 6336 
1  1127 J. R. Tillerson, 6337 
1  1127 C.K. Ho, 6731 
1  1127 T. R. Mancini, 6337 
1  1127 G. J. Kolb, 6335 
1  1137 R. E. Finley, 6337 
1  1137 H. D. Passell, 6733 
1  1137 E. H. Richards, 6733 
 
 
1 MS  0899 Technical Library, 9536 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
U.S. Department of Energy 
 
1 K. Lynn kevin.lynn@hq.doe.gov 
1 S. Stephens scott.stephens@ee.doe.gov 
 
 
National Renewable Energy Laboratory 
 
1 N. Blair  Nate.Blair@nrel.gov 
1 I. Baring-Gould Ian.Baring-Gould@nrel.gov 
1 R. Margolis  Robert.Margollis@nrel.gov 
1 B. Marion  Bill.Marion@nrel.gov 
1 S. Kurtz  Sarah.Kurtz@nrel.gov 
1 A. Dobos  Aron.Dobos@nrel.gov 
1 B. Von Roedern Bolko.von.Roedern@nrel.gov 
 
Other Recipients 
 
1 D. Menicucci dmenicucci1@comcast.net 
1 D. King  DavidLKing@aol.com 
1 M. Ropp  michael.ropp@sdstate.edu 
1 T. Hoff  tomhoff@cleanpower.com 
1 S. Klein  klein@engr.wisc.edu 
1 W. Beckman  beckman@engr.wisc.edu
