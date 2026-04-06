---
title: "T13 Report PV Performance Modeling Methods and Practices FINAL March 2017"
orthodoxy: "SME reference (converted from PDF)"
technologies: [solar]
tags: [pdf, sme reference, pv, solar]
weight: 1.0
source_pdf: "T13_Report_PV_Performance_Modeling_Methods_and_Practices_FINAL_March_2017.pdf"
---

<!-- Extracted text; edit frontmatter and body as needed. -->

PV Performance Modeling Methods 
and Practices 
Results from the 4th PV Performance 
Modeling Collaborative Workshop 
 
 
 
 
 
 
 
 
 
 
Report IEA-PVPS T13-06:2017 

 
INTERNATIONAL ENERGY AGENCY 
PHOTOVOLTAIC POWER SYSTEMS PROGRAMME 
 
 
 
PV Performance Modeling Methods and Practices 
Results from the 4th PV Performance Modeling  
Collaborative Workshop 
 
 
 
 
IEA PVPS Task 13, Subtask 2 
Report IEA-PVPS T13-06:2017 
March 2017 
 
ISBN 978-3-906042-50-3 
 
Author  
Joshua S. Stein PhD (jsstein@sandia.gov) 
Sandia National Laboratories 
Editor 
Boris Farnung (Boris.Farnung@ise.fraunhofer.de)  
Fraunhofer ISE 
 
  
Contributing Authors 
Marion Schroedter-Homscheidt 
Karel De Brabandere 
Marcel Suri 
Jan Remund 
Manajit Sengupta 
Elke Lorenz 
Anton Driesse 
Stefan Winter 
Annette Hammer 
Thomas Huld 
Mitchell Lee 
Giorgio Belluardo 
Fotis Mavromatakis 
Benjamin Duck 
Markus Schweiger 
Werner Herrmann 
Bruce H. King 
Janine Freeman 
Teresa Zhang 
Gianluca Corbellini 
Christian Reise 
Hendrik Holst 
Jose E. Castillo-Aguilella 
Bruno Wittmer 
Tomas Cebecauer 
Aron P. Dobos 
Paul Gibbs 
Angele Reinders 
Matthew Boyd 
Gabi Friesen 
Benjamin Matthiss 
Steve Ransome 
Jürgen Sutterlueti 
Yuzuru Ueda 
Roger French 
 
3 
 
Table of Contents 
Table of Contents ............................................................................................................................... 3 
Foreword ............................................................................................................................................ 6 
Acknowledgements ............................................................................................................................ 8 
Executive Summary .......................................................................................................................... 10 
1 Introduction .............................................................................................................. 11 
2 Performance Modeling of PV Systems ...................................................................... 15 
2.1 Standard Sequence of PV Performance Modeling Steps ...................................................15 
2.2 PV System Design Parameters ...........................................................................................15 
2.3 Irradiance and Weather Data Sources ...............................................................................16 
2.4 Translating Irradiance to the Plane of the Array ...............................................................17 
2.5 Estimation of Shading, Soiling, and Reflection Losses .......................................................17 
2.6 Effective Irradiance ............................................................................................................18 
2.7 Estimation of cell temperature ..........................................................................................20 
2.7.1 Faiman Module Temperature Model ........................................................................ 20 
2.8 Current and Voltage (I-V) Models ......................................................................................20 
2.8.1 Diode Equivalent-Circuit Model ................................................................................ 20 
2.8.2 Fixed-Point Models ................................................................................................... 21 
2.9 DC Wiring and Mismatch Losses ........................................................................................21 
2.10 DC to AC Conversion Efficiency ..........................................................................................22 
2.11 AC Wiring and Transformer Losses ....................................................................................23 
3 Workshop Presentation Summaries ......................................................................... 24 
3.1 Session 1: Solar Resource Data and Uncertainty ...............................................................24 
3.1.1 Satellite- and Camera-derived Irradiance Data for Applications in Low Voltage Grids 
with Large PV Shares ................................................................................................. 25 
3.1.2 Evaluation of Satellite Irradiation Data at 200 Sites in Western Europe .................. 27 
3.1.3 Uncertainty of Satellite Based and Ground Based Solar Resource Assessment ....... 28 
3.1.4 Accuracy of Meteonorm 7.1 ..................................................................................... 30 
3.1.5 Next-Generation Satellite Modeling for NREL’s National Solar Radiation Data Base32 
3.1.6 Local and Regional PV Power Forecasting Based on PV Measurements, Satellite 
Data and Numerical Weather Predictions ................................................................ 33 
3.1.7 Dynamic Uncertainty of Irradiance Measurements – Illustrations from a Study of 42 
Radiometers .............................................................................................................. 34 
3.1.8 Towards an Energy-based Parameter for Photovoltaic Classification ...................... 36 
4 
 
3.1.9 PVKLIMA- Time Series of Spectrally Resolved Irradiance Data from Satellite 
Measurements .......................................................................................................... 37 
3.2 Session 2: Spectral Corrections for PV Performance Modeling ........................................ 39 
3.2.1 Satellite-based Estimates of the Influence of Solar Spectr um Variations on PV 
Performance .............................................................................................................. 39 
3.2.2 Combined Air Mass and Precipitable Water Spectral Correction for PV Modeling .. 41 
3.2.3 Sensitivity Analysis and Uncertainty Evaluation of Simulated Clear- Sky Solar Spectra 
Using Monte Carlo Approach .................................................................................... 43 
3.2.4 Spectral Corrections for PV Performance Modeling ................................................. 45 
3.2.5 Improved Prediction of Site Spectral Impact ............................................................ 46 
3.2.6 Impact of Spectral Irradiance on Energy Yield of PV Modules Measured in Different 
Climates ..................................................................................................................... 48 
3.3 Session 3: Soiling and Snow, and Other System Derating Factors .................................... 50 
3.3.1 Impact of Soiling on PV Module Performance for Various Climates ........................ 50 
3.3.2 Overview of Sandia’s Soiling Program: Description of Experimental Methods and 
Framework for a Quantitative Soiling Model ............................................................ 51 
3.3.3 Validation of Models for Energy Losses due to Snowfall on PV Systems.................. 53 
3.4 Session 4: Bifacial PV Modeling Challenges ...................................................................... 56 
3.4.1 Introduction to Bifacial Modeling Challenges ........................................................... 56 
3.4.2 Simulation and Validation of Modeling of Bifacial Photovoltaic Modules ............... 57 
3.4.3 Realistic yield expectations for bifacial PV systems –  an assessment of announced, 
predicted and observed benefits .............................................................................. 60 
3.4.4 Modeling of the Expected Yearly Power Yield on Building Façades in Urban Regions 
by Means of Ray Tracing ........................................................................................... 60 
3.4.5 Multi-Year Study of Bifacial Energy Gains Under Various Field Conditions .............. 62 
3.5 Session 5: PV Modeling Applications: Modeling Tool Updates ........................................ 65 
3.5.1 Latest Features of PVsyst .......................................................................................... 65 
3.5.2 pvSpot - PV Simulation Tool for Operational PV Projects ......................................... 68 
3.5.3 Recent and Planned Improvements to the System Advisor Model (SAM) ............... 69 
3.5.4 Helioscope ................................................................................................................. 71 
3.5.5 Performance Modeling of PV Systems in a Virtual Environment.............................. 72 
3.6 Session 6: Field Monitoring and Validation of PV Performance Models .......................... 74 
3.6.1 High-Speed Monitoring of Multiple Grid-Tied PV Array Configurations ................... 74 
3.6.2 Field Data from Different Climates for the Validation of Module Performance 
Models ....................................................................................................................... 75 
3.6.3 Comparison and Validation of PV System and Irradiance Models ............................ 76 
3.6.4 The “best” PV Model Depends on the Reason for Modeling .................................... 77 
3.6.5 Using Advanced PV and BoS Modeling and Algorithms to Optimize the Performance 
of Large Scale Utility Applications ............................................................................. 80 
3.6.6 System Performance and Degradation Analysis of Different PV Technologies ........ 84 
5 
 
3.7 Poster Session ....................................................................................................................87 
3.7.1 Big-data Analytics of Real- world I -V, Pmp Time Series to Validate Models and Ex -
tract Mechanistic Insights to Lifetime Performance ................................................. 89 
References ........................................................................................................................................ 92 
 
6 
 
Foreword 
The International Energy Agency (IEA), founded in November 1974, is an autonomous body within 
the framework of the Organization for Economic Co -operation and Development (OECD) which 
carries out a comprehensive programme of energy co -operation among its member countries. 
The European Union also participates in the work of the IEA. Collaboration in research, develo p-
ment and demonstration of new technologies has been an important p art of the Agency’s Pr o-
gramme.  
The IEA Photovoltaic Power Systems Programme (PVPS) is one of the collaborative R&D Agre e-
ments established within the IEA. Since 1993, the PVPS participants have been conducting a varie-
ty of joint projects in the application of photovoltaic conversion of solar energy into electricity. 
The mission of the IEA PVPS Technology Collaboration Programme is: To enhance the internatio n-
al collaborative efforts which facilitate the role of photovoltaic solar energy as a cornerstone in 
the transition to sustainable energy systems. The underlying assumption is that the market for PV 
systems is rapidly expanding to significant penetrations in grid-connected markets in an increasing 
number of countries, connected to both the distribution net work and the central transmission 
network. 
This strong market expansion requires the availability of and access to reliable information on the 
performance and sustainability of PV systems, technical and design guidelines, planning methods, 
financing, etc., to be shared with the various actors. In particular, the high penetration of PV into 
main grids requires the development of new grid and PV inverter management strategies, greater 
focus on solar forecasting and storage, as well as investigations of the economic and technological 
impact on the whole energy system. New PV business models need to be developed, as the d e-
centralised character of photovoltaics shifts the responsibility for energy generation more into the 
hands of private owners, municipalities, cities and regions. 
IEA PVPS Task 13 engages in focusing the international collaboration in improving the reliability of 
photovoltaic systems and subsystems by collecting, analyzing and disseminating information on 
their technical performance and failures,  providing a basis for their technical assessment, and 
developing practical recommendations for improving their electrical and economic output. 
The current members of the IEA PVPS Task 13 include: 
Australia, Austria, Belgium, China, Denmark, Finland, Franc e, Germany, Israel, Italy, Japan, Mala y-
sia, Netherlands, Norway, SolarPower Europe, Spain, Sweden, Switzerland, Thailand and the Unit-
ed States of America.   
This report focusses on data, methods, and models for predicting the performance of photovolt a-
ic systems in the field. Such performance varies as a function of component characteristics, sy s-
tem design, site characteristics, and weather and climate data. These topics are documented and 
organized by the PV Performance Modeling Collaborative (PVPMC). The report is divided into two 
main sections: (1) a section describing a set of standardized modeling steps for photovoltaic pe r-
formance modeling, and (2) a summary of presentations made on these topics at the 4
th PV Per-
formance Modeling Collaborative Workshop held in Cologne, Germany at the headquarters of 
TÜV Rheinland on October 22 -23, 2015. These summaries provide a good overview of achiev e-
ments in this area from IEA member countries. 
The editor of the document is Boris Farnung, Fraunhofer ISE, Freiburg, Germany. 
7 
 
The report expresses, as nearly as possible, the international consensus of opinion of the Task 13 
experts on the subject dealt with. Further information on the activities and results of the Task can 
be found at: http://www.iea-pvps.org. 
8 
 
Acknowledgements 
This technical report received valuable contributions from many  IEA-PVPS Task 13 members and 
other international experts, all of whom are listed as contributing authors . We are thankful to all 
the presenters at the 4th PVPMC workshop (named in later sections of this report). In addition, we 
thank the following individuals for their careful reviews and suggestions:  
• Ulrike Jahn   TÜV Rheinland Energy 
• Cathy Zhou  TÜV Rheinland Energy 
• Nils Reich  Fraunhofer ISE 
• Helen Rose Wilson Fraunhofer ISE 
• Bert Herteleer  CAT Projects 
• Wilfried van Sark Utrecht University 
Sandia National Laboratories is a multi- mission laboratory managed and operated by San dia Cor-
poration, a wholly owned subsidiary of Lockheed Martin Corporation, for the U.S. Department of 
Energy’s National Nuclear Security Administration under contract DE-AC04-94AL85000. 
 
  
9 
 
List of Abbreviations  
AM  relative air mass 
AMa absolute air mass 
AOD aerosol optical depth 
AOI  angle of incidence 
APE average photon energy 
AVHRR Advanced Very High Resolution Radiometer 
CAMS Copernicus Atmospheric Monitoring Service 
CMV PV power forecasts based on satellites 
DHI  diffuse horizontal irradiance 
DNI  direct normal irradiance 
EURAC European Academy  
FARMS Fast All-sky Radiation Model for Solar applications 
GHI  global Horizontal Irradiance 
GOES Geostationary Operational Environmental Satellites 
GSIP Global Solar Insolation Project 
ISFH Institute for Solar Energy Research Hamelin 
JRC  Joint Research Center  
KNMI Koninklijk Nederlands Meteorologisch Instituut 
LCE  life cycle emissions 
LCOE Levelized cost of electricity 
LFM loss factors model 
MACC Monitoring Atmospheric Composition and Climate 
MPP maximum power point 
MPPT maximum power point tracking  
MPR  module performance ratio 
MSG Meteosat Second Generation Satellite 
NOAA National Oceanic Atmospheric Agency 
NREL National Renewable Energy Laboratory 
NSRDB National Solar Radiation Data Base 
NWP numerical weather predictions 
PATMOS-x Pathfinder Atmospheres-Extended algorithm 
PSM physical solar model 
PV  photovoltaic 
PVPMC Photovoltaic Performance Modeling Collaborative 
PWV  precipitable water vapor 
Pwat precipitable water content 
QE  quantum efficiency 
SOLIS Synoptic Optical Long-term Investigation of the Sun 
SMARTS Simple Model of the Atmospheric Radiative Transfer for Sunshine 
SR   spectral response 
STC  standard test conditions 
TMY typical meteorological year 
 
10 
 
Executive Summary 
In 2014, the IEA PVPS Task 13 added the PVPMC as a formal activity to its technical work plan for 
2014-2017. The goal of this activity is to expand the reach of the PVPMC to a broader internatio n-
al audience and help to reduce PV performance modeling uncertainties worldwide. One of the 
main deliverables of this activity is to host one or more PVPMC  workshops outside the US to fo s-
ter more international participation within this collaborative group. 
This report reviews the results of the first in a series of these joint IEA PVPS Task 13/PVPMC work-
shops. The 4th PV Performance Modeling Collaborative Wo rkshop was held in Cologne, Germany 
at the headquarters of TÜV Rheinland on October 22-23, 2015. 
Approximately 220 solar energy experts from over 30 countries and four continents gathered for 
two days at the headquarters of TÜV Rheinland in Cologne Germany  to discuss and share results 
related to predicting the performance and monitoring the output from solar photovoltaic (PV) 
systems. The workshop was divided into six topical sessions exploring advances in the areas of 
solar resource assessment, effects of irradiance spectrum on PV performance, soiling losses, bifa-
cial PV performance, modeling tools, and monitoring applications. This workshop is the fourth and 
largest in a series of workshops organized by the PV Performance Modeling Collaborative or 
PVPMC (pvpmc.sandia.gov), a group started by Sandia National Laboratories in 2010 to bring t o-
gether stakeholders with the aim of advancing the “state of the art” in PV performance predic-
tion. The PVPMC collects information from the community and shares it on the web and in a set 
of open source code libraries in Matlab and Python. 
Highlights from the workshop include the following: 
• Validation and comparison of four satellite irradiance products across Europe show that 
these data sets are becoming more accurate and that differences between different 
products are becoming smaller. 
• A number of new spectral irradiance data sets are being developed from satellite data 
sources. The general availability of such data has promise to reduce uncertainty in PV per-
formance modeling since spectral mismatch is one of the major sources of uncertainty in 
current tools. 
• Two new spectral mismatch models were introduced at the workshop that utilize readily 
available meteorological data such as precipitable water, clearness index, and air mass to 
better estimate the spectral mismatch in PV performance. Model developers at the work-
shop expressed their interest in including such models in future releases of software 
packages. 
• Soiling from dust and snow continue to be major causes of energy loss for PV systems, es-
pecially in certain regions. Estimating these losses in detail in performance predictions 
continues to be a challenge. 
• Modeling and field data for bifacial PV modules and systems were presented. It is increas-
ingly clear that significant performance gains are available from bifacial technologies; 
however, current modeling tools are unable to accurately predict energy production from 
bifacial modules. 
• Field monitoring of PV systems is still in need of standardized methods to ensure high 
quality data is collected. Several experts in this area presented examples of good practice, 
but these examples are not typical of system monitoring in general. 
This report begins with a technical overview of PV performance modeling steps and then  pro-
ceeds to summarize each of the technical presentations made at the workshop. Original presenta-
tion files are all available on the PVPMC website [1]. 
11 
 
1 Introduction 
The broad application of photovoltaic (PV) technologies to the energy system is still a re latively 
new field and as such, best practices and innovative methods and policies are actively being d e-
veloped and tested in different countries. The latest information on new advances in methods 
and algorithms can be difficult to obtain, especially if presented at industry conferences, in ac a-
demic journals, or workshops, which are usually only accessible to a limited group of stakehold-
ers.  
One area for which efficient sharing of this information is of particular importance is PV perfo r-
mance and reliability modeling. Because nearly all PV system investment is made before systems 
begin producing energy and revenue, PV plant or technology investment risk largely depends  on 
the confidence that investors have that the plant/technology will perform in the field as predicted 
for the expected lifetime. The cost of financing this risk is significantly influenced by uncertainty—
either real or perceived — in long-term performance calculations. Disseminating best practices in 
this area is critical for reducing costs associated with perceived uncertainty. Eliminating perceived 
uncertainty will result in greater focus on real uncertainties that are known, measurable, and ea s-
ier to quantify and address: for example, the uncertainty of what the weather and irradiance will 
be in the future. 
The lack of available information about PV performance modeling methods is an important co n-
tributor to perceived uncertainty. This was one outcome of a blind study conducted at Sandia 
National Laboratories’ first PV Performance Modeling Workshop in 2011  [2]. For this study, 20 
participants were provided with technical descriptions of three PV systems and one year of meas-
ured weather and irradiance data and were asked to predict the performance of the systems u s-
ing the model of their choice. The participants represented a range of PV professionals from PV 
model developers, integrators, independent engineers, and academia. Together, they applied  a 
total of seven different performance models, and several participants applied  more than one 
model. The results were combined and compared to the actual performance of the system, which 
was carefully monitored— but not shared with the participants before the study. The results were 
similar for all three systems. 
 
Figure 1: Example results of a blind modeling study that led to the start of the PV Performance 
Modeling Collaborative. 
(Wh/y) 
12 
 
 Figure 1 shows an example for one of the systems. Most of the models over-predicted system 
performance. The variation of results did not dep end on which model was used, but rather who 
ran the model and “how” the model was set up and parameterized. PV performance models r e-
quire numerous of inputs and sub-model choices to be made, and it was found that these choices 
made by model operators result in a significant amount of uncertainty. These results led to the 
formation of the Photovoltaic Performance Modeling Collaborative (PVPMC), and an ever-growing 
community interested in better understanding and reducing the uncertainty inherent in PV pe r-
formance modeling. 
Table 1: List of PVPMC Workshops. 
Workshop Location Date 
1st PVPMC Workshop Albuquerque, NM USA 20-21 September 2011 
2nd PVPMC Workshop Santa Clara, CA USA 1-2 May, 2013 
3rd PVPMC Workshop Santa Clara, CA USA 4 May 2014 
4th PVPMC Workshop Cologne, Germany 22-23 October 2015 
5th PVPMC Workshop Santa Clara, CA USA 9 May 2016 
6th PVPMC Workshop Freiburg, Germany 24-25 October 2016 
7th PVPMC Workshop Lugano, Switzerland 30 April 2017 
8th PVPMC Workshop Albuquerque, NM USA 9-10 May 2017 
 
In 2014, the IEA PVPS Task 13 added the PVPMC as a formal activity to  its technical portfolio for 
2014-2017. The goal of this activity is to expand the reach of the PVPMC to a broader internatio n-
al audience and help to r educe PV performance modeling uncertainties worldwide. One of the 
main deliverables of this activity is to host one or more PVPMC workshops outside the US to fo s-
ter more international participation in this collaborative group. 
This report reviews the results of the first in a series of these joint IEA PVPS Task 13/PVPMC work-
shops. The 4th PV Performance Modeling Collaborative Workshop was held in Cologne, Germany 
at the headquarters of TÜV Rheinland on October 22-23, 2015. 
Approximately 220 solar energy exp erts from over 30 countries and four continents  (Figure 2) 
gathered for two days at the headquarters of TÜV Rheinland in Cologne Germany to discuss and 
share results related to predicting the performance and monitoring the output from solar PV sy s-
tems. The workshop was divided into six topical sessions exploring advances in the areas of solar 
resource assessment, effects of irradiance spectrum on PV performance, soiling losses, bifacial PV 
performance, modeling tools, and monitoring applications. This workshop is the fourth and larg-
est in a series of workshops organized by the PVPMC (pvpmc.sandia.gov), a group started by San-
dia National Laboratories in 2010 to bring tog ether stakeholders with the aim of advancing the 
“state of the art” in PV performance prediction. The PVPMC collects information from the co m-
munity and shares it on the web and in a set of open source code libraries in Matlab and Python. 
 
13 
 
 
Figure 2: Participants by country at the 4th PV Performance Modeling Workshop in Cologne, Ge r-
many. 
Highlights from the workshop include the following: 
• Validation and comparison of four satellite irradiance products across Europe show that 
these data sets are becoming more accurate and that differences between different 
products are becoming smaller. 
• A number of new spectral irradiance data sets are being developed from satellite data 
sources. The general availability of such data has promise to reduce uncertainty in PV per-
formance modeling since spectral mismatch is one of the major sources of uncertainty in 
current tools. 
• Two new spectral mismatch models were introduced at the workshop that utilize readily 
available meteorological data such as precipitable water, clearness index, and air mass to 
better estimate the spectral mismatch in PV performance. Model developers at the work-
shop expressed their interest in including such models in future releases of software 
packages. 
• Soiling from dust and snow continue to be major causes of energy loss for PV systems, es-
pecially in certain regions. Estimating these losses in detail in performance predictions 
continues to be a challenge. 
• Modeling and field data for bifacial PV modules and systems were presented. It is increas-
ingly clear that significant performance gains are available from bifacial technologies; 
however, current modeling tools are unable to accurately predict energy production from 
bifacial modules. 
• Field monitoring of PV systems is still in need of standardized methods to ensure high 
quality data is collected. Several experts in this area presented examples of good practice, 
but these examples are not typical of system monitoring in general. 
Clear consensus was expressed by the participants  on one point: The Solar Energy Team of TÜV 
Rheinland did a fantastic job of hosting the modeling  workshop. Their high quality, comfortable 
facilities, and gracious attention to detail allowed all participants to focus on the technical pro-
gram and use our valu able time together as a group for developing and sustaining collaborations 
to improve PV performance modeling and monitoring. 

14 
 
 
Figure 3: Participants at the 4th PV Performance Modeling Collaborative Workshop. 
The technical content of the report starts in Section 2  with a brief summary of PV performance 
modeling steps and methods so that the summaries of the workshop sessions that follow in Sec-
tion 3 can be read within the technical context of the field.  More details on the modeling steps 
and the various sub -models that are used in each step are available on the PVPMC website’s 
Modeling Steps section ( https://pvpmc.sandia.gov). This includes approximately 200 webpages 
with technical model descriptions contributed by PVPMC members.  Finally, conclusions are made 
with recommendations for future related activities. 

15 
 
2 Performance Modeling of PV Systems 
Models, in the context of this report, are mathematical or conceptual representations of real sy s-
tems. They are generated for the purpose of understanding and predicting behavior that can be 
measured or observed. In the context of PV systems, models are used to understand and predict 
energy or power output from PV systems un der a wide range of environmental, design, and site 
conditions. It is wise to view any and all PV performance models with a certain amount of caution  
as all of these models make simplifying assumptions that result in some degree of mismatch b e-
tween model r esults and measurements.  Furthermore, all measurements of PV system perfo r-
mance (e.g., current, voltage, temperature, tilt and azimuth angles, etc.) have inherent uncertai n-
ty. A favorite quote of modelers, which is attributed to George Box [3], is “Essentially, all models 
are wrong, but some are useful. ” The PVPMC’s aim is to help modelers learn about and distin-
guish between available models and find the most useful ones for their purpose. 
2.1 Standard Sequence of PV Performance Modeling Steps 
The approach followed by the PVPMC to describe PV performance modeling is to follow the ene r-
gy, which originates from the S un as light, travels through space and E arth’s atmosphere, and 
reaches a PV array, where it is converted to electrical energy.  At each step in this jo urney, energy 
is transferred and some portion of it is “lost” (usually as heat).  The goal of PV performance mo d-
els is to calculate or estimate how much of the energy is converted to usable and valuable electri-
cal energy. This is usually done by tracking energy conversion and loss at each of these steps. 
The general steps are listed below 
1. Define PV system design parameters 
2. Choose irradiance and weather data  
3. Translate irradiance data to the plane of the array 
4. Estimate optical losses from shading, soiling, and reflections on the surface of the array or 
module 
5. Estimate “effective” irradiance 
6. Estimate the cell temperature of the PV cells 
7. Estimate the current (I) and voltage (V) characteristics of the PV module  
8. Estimate the DC wiring and mismatch losses 
9. Estimate the DC to AC conversion losses 
10. Estimate the AC wiring and transformer losses. 
In the sections that follow, we will provide more details about the assumptions and calculations 
that are made to estimate the quantities listed above.  When these areas overlap with present a-
tions made by workshop speakers, we will point these out so that the reader can better choose 
how to read the presentation summaries presented in Section 3. 
It is also worth noting that PV technologies and system designs are evolving and quite varied.  For 
the purpose of clarity, we will assume a conventional grid -connected, flat-plate PV system with a 
string inverter for the discussion below.  For other types of PV technology (e.g., concentrating PV) 
or system designs (e.g., DC optimizer s, and systems based on micro -inverters), some of the steps 
presented below would have to be altered, although the approach would be similar. 
2.2 PV System Design Parameters 
For the purpose of modeling PV system performance , the following design and site parameters 
are generally used. It should be noted that the modeling steps are generally applie d to a typical 
system design of a single inverter connected to x number of strings of y modules each.  There is a 
16 
 
wide variety of variants to this typical design, such as micro -inverters, multi-port inverters with 
separate MPPT trackers, etc.  Slight modifications to the modeling  steps or order in which the 
steps are followed are usually required for simulations of these different systems. 
Site Parameters 
• Latitude and longitude 
• Elevation 
System Design Parameters 
• Inverter model name and performance parameters 
• Module model name and performance parameters 
• Number of modules per series string 
• Number of series strings per array 
• Cable lengths, types and cross sections 
• Tilt (𝜃𝜃𝑇𝑇) and azimuth of the array (or tracking angle algorithm for tracked arrays) 
• Albedo of the ground (or roof) surface) 
• Horizon map showing potential for shading from obstructions 
2.3 Irradiance and Weather Data Sources 
Irradiance and weather data for at least a full year must be gathered in order to run a PV perfo r-
mance model. Time steps of one hour or less are standard. Depending on the location of interest, 
data is available from a number of public and private sources. This data can be from historical and 
ongoing ground-based measurement stations and networks, modeled from satellite imagery, or 
modeled from general weather observations in places where irradiance is not measured directly.  
Frequently, synthetic annual data sets are made available that are meant to be representative of 
longer trends in irradiance. These “typical” meteorological years are used to estimate  future per-
formance from PV systems. More recently, performance simulations have been  run using numer-
ous different irradiance data sets in order to estimate the uncertainty due to estimating future 
weather conditions. 
Ground measurements from well -maintained, calibrated radiometers are considered to be the 
best and most accurate source of irradiance data.  However, such stations are not common and 
finding such data near the location of interest is usually not possible, unless a station has been 
installed for that purpose, in which case the length of the record is usually short.  Thus uncertain-
ties arise from assuming that the available irradiance is similar to the irradiance expected at the 
site of interest.  Microclimatic differences can be important, especially in areas with topographic 
variability. 
Satellite-based model results have improved significantly in  recent years and offer a good co m-
promise to sparse ground-based data. Available in grids that cover most inhabited land areas, this 
data is generally available on an hourly basis and sometimes every 30 or even 15 minutes. Various 
sources exist for this da ta, including government agencies, such as NASA, NOAA, German Aer o-
space Agency, and others.  The finest resolution data (in time and space) is available from private 
companies (e.g., SolarGIS, Clean Power Research, etc.) for a fee. 
Irradiance data is reported as three components: direct normal irradiance (DNI), global horizontal 
irradiance (GHI), and diffuse horizontal irradiance (DHI).   These components are typically made 
with broadband instruments.  From these components, the intensity on the plane of the PV array 
can be estimated using transposition models. Since it is easier to measure GHI, it is common prac-
tice to estimate DNI and DHI from GHI using a decomposition model (e.g., DISC  [4], DIRINT [5]). 
Use of such models introduces additional uncertainty. 
17 
 
2.4 Translating Irradiance to the Plane of the Array 
Irradiance on the plane of the array is equal to the sum of the beam irradiance, the sky diffuse 
irradiance and the ground -reflected irradiance.  Beam irradiance is calculated as DNI*cos(AOI), 
where AOI is th e angle of incidence of direct irradiance from the S un to the plane of the array.  
Ground-reflected irradiance depends on GHI, the tilt angle of the array, and the reflectivity of the 
ground, typically expressed as the albedo.   Typical values for common surface types are available 
on the PVPMC website [6]. 
Sky diffuse irradiance has been the subject of many studies aimed at developing models to est i-
mate it from measured irradiance components, array tilt  (𝜃𝜃𝑇𝑇), and other factors.  The simplest 
formulation assumes that the intensity of the diffuse light is equal in all parts of the sky.  This iso-
tropic model estimates diffuse sky irradiance on the plane of the array as: 
𝐸𝐸𝑠𝑠𝑠𝑠= 𝐷𝐷𝐷𝐷𝐷𝐷�1 + 𝑐𝑐𝑐𝑐𝑐𝑐(𝜃𝜃𝑇𝑇)
2 � 
In fact, the isotropic model of the  sky is not very accurate.  Due to scattering processes in the a t-
mosphere, the intensity of the diffuse light is enhanced near the position of the Sun. Models that 
include the effects of this circumsolar brightening more accurately estimate the diffuse light avail-
able to a PV array. One of the most widely used models that include  circumsolar brightening was 
proposed by Hay and Davies [7]. It has the following form: 
𝐸𝐸𝑠𝑠𝑠𝑠= 𝐷𝐷𝐷𝐷𝐷𝐷�𝐷𝐷𝐷𝐷𝐷𝐷
𝐸𝐸𝑎𝑎
𝑐𝑐𝑐𝑐𝑐𝑐(𝐴𝐴𝐴𝐴𝐷𝐷) + �1 − 𝐷𝐷𝐷𝐷𝐷𝐷
𝐸𝐸𝑎𝑎
� 1 + 𝑐𝑐𝑐𝑐𝑐𝑐(𝜃𝜃𝑇𝑇)
2 � 
where Ea is extraterrestrial irradiance in (W/m 2), which can be estimated from the day of year, 
since Earth’s orbit is elliptical [8] . The additional terms and factors in the Hay and Davies model 
are intended to account for the brightening around the solar disk. 
Many other models have been proposed, some of which include a term to represent a slight 
brightening of the sky at the horizon (e.g., [9-10]). 
 
2.5 Estimation of Shading, Soiling, and Reflection Losses 
The light that is incident on the plane of the array (incid ent on the top surface of the module)  is 
not the same as the light that is available for conversion to energy by the PV system.  Physical ob-
jects surrounding the array such as buildings, poles, and other parts of the PV system can obstruct 
the light that is  able to reach the PV array.  One of the goals of system design is the minimization 
of shading, but  some shading may be unavoidable , especially in residential rooftop sys tems. The 
effect of shading is quantified by use of a horizon map, which indicates the position of obstructing 
objects in relation to the path of the Sun across the sky throughout the year. Times when the sys-
tem is shade d can be estimated ; the effect is typically simulated by subtracting the direct beam 
irradiance from the in-plane value for those times. The effects of shading on a part of the PV array 
is more complicated to account for and depends on the location of the series strings in the array 
and other electrical wiring details.  
Dust and debris on the surface of the PV modules reduces the available light.  The composition of 
the dust and the environment and climate of the site all play a role in the severity of this effect.  
Certain parts of the world are mu ch more affected by these “soiling” losses.  Section 3.3  of this 
report provides more details. 
The amount of light that is reflected by  the front of the PV modules varies with the angle of inc i-
dence of the light on the surface.  Angles from 0˚ to about 50˚ generally result in very little refle c-
18 
 
tion, but for angles greater than 50 ˚, reflections increase as the angle increases.   Figure 4 shows 
this effect as predicted using a model developed by Martin and Ruiz [11] .  The angular factor is 
the fraction of the light transmitted through the module surface to the PV cells .  Lower values of 
ar are used to represent the effect of antireflective coatings on the front glass pane, which main-
tains an angular factor near 1 at higher angles of incidence. 
 
Figure 4: Relative reflectance of a module surface as a function of incidence angle  and empirical 
parameter, ar, for a model developed by Martin and Ruiz [11]. 
2.6 Effective Irradiance 
Effective irradiance (Ee) is the light that is directly available to be converted into electrical current  
by the PV material. It is essentially the POA irradiance minus several loss factors including: 
• Soiling losses  
• Reflection losses 
• Shading losses 
• Spectral losses 
All of these losses have been discussed above except for spectral losses. Spectral losses are due to 
the fact that PV materials are able to absorb light only in a limited range of the solar spectrum.  
Figure 5 shows a representation of the s olar spectrum. Outside Earth’s atmosphere, the solar 
spectrum is similar to the radiation emitted by a blackbody source at 5 778°C. Atmospheric con-
stituents such as water (H2O), CO2, ozone, and other gases absorb light in certain wavelengths and 
alter the extraterrestrial spectrum  at Earth’s surface. The terrestrial spectrum changes over time 
and location due to variability in the atmosphere and as a function of the path length of the S un’s 
direct beam through the atmosphere.  This path length is represented by a relative, non -
dimensional quantity called optical air mass (AM) and calculated as a function of the solar zenith 
angle and the ground elevation.  In space, the air mass value is zero and at sea level with the Sun 
at a zenith angle of zero degrees (directly overhead), the air mass value is equal to 1. 
The response of a PV device to various wavelengths of light is called the Spectral Response (SR) 
and is in units of A/W.  Figure 6 shows typical spectral response curves for a number  of different 
PV technologies. 

19 
 
 
Figure 5: Typical solar spectrum. Source: [12] 
 
Figure 6: Representative spectral response curves for typical PV cell technologies from the PVPMC 
website [13]). 
 
One expression for Ee is: 
𝐸𝐸𝑒𝑒= 𝑓𝑓1 �� 𝐸𝐸𝑏𝑏𝑓𝑓2 + 𝑓𝑓𝑠𝑠�𝐸𝐸𝑠𝑠𝑠𝑠+ 𝐸𝐸𝑔𝑔�� /𝐸𝐸0� 𝑆𝑆𝑆𝑆 
where f1 is a f actor accounting for the spectral effects, f2 is a function  of AOI that describes the 
reflection effects (e.g., Figure 4), fd is the fraction of the diffuse irradiance used by the module and 
typically equals 1 for flat plate modules  but can be <1 for concentrating PV modules.  SF is the 
soiling factor ( dimensionless), which is the fraction of light that is not obstructed by the soiling 

20 
 
layer on the PV device. E 0 is the reference irradiance (1  000 W/m2). Eb, Esd, and Eg are beam, sky-
diffuse, and ground reflected broadband irradiances, respectively. 
The spectral factor f1 is usually expressed as a function of quantities that are easily measured, 
such as air mass [14], air mass and relative humidity (see Section 3.2.2), or air mass and clearness 
index (see Section 3.2.5). 
2.7 Estimation of cell temperature 
The operating temperature of PV modules and the cells inside the modules affects the perfo r-
mance of the PV system.  Typical PV cells lose efficiency as temperatures rise s. Typical rates are  
 -0.3 to -0.5% per °C above STC. For this reason, it is necessary to estimate the operating tempera-
ture of the PV modules in the array as it changes during the day.  Modules change temperature in 
response to changes in the plane-of-array (POA) irradiance, ambient air temperature, wind speed, 
and even relative humidity (humid air has a higher heat capacity). Most module and cell tempera-
ture models assume a steady -state temperature balance and therefore should be used with time 
steps greater than ~15 min.  Transient thermal models have been developed, but are not y et 
available in commercial PV performance models.   
2.7.1 Faiman Module Temperature Model 
A popular model for module temperature that is used in the PVsyst model is based on Faiman [15] 
and has the following form:  
𝑇𝑇𝑐𝑐= 𝑇𝑇𝑎𝑎+ 𝛼𝛼𝐸𝐸𝑒𝑒(1 − 𝜂𝜂𝑚𝑚)
𝑈𝑈0 + 𝑈𝑈1𝑊𝑊𝑆𝑆    
where Ta is air temperature (°C), α is the absorptance of the module (typical value is 0.9), ηm is the 
efficiency of the module (typically 0.08 -0.2), WS is the wind speed (m/s).  U0 is the constant heat 
transfer coefficient (Wm-2°C-1) and U1 is the convective heat transfer coefficient (Wm-3 s °C-1). Typ-
ical values for U 0 and U1 range from 23.5 to 26.5 Wm -2 °C-1 and 6.25 to 7.68 Wm -3 s °C-1, respec-
tively. Other module temperature models are also available (e.g., [14; 16-18]. 
2.8 Current and Voltage (I-V) Models 
A PV cell, module, or series string of modules under illumination has a characteristic relationship 
between the current generated by the device and the voltage applied to the circuit.  The charac-
teristic is called the IV curve and estimating this curve or points  on the curve is the aim of the 
models described in this step.  There are three basic types of IV models: equivalent circuit diode 
models, semi-empirical “point” models, and simple efficiency models. 
2.8.1 Diode Equivalent-Circuit Model 
Diode equivalent-circuit models assume that the performance of a PV module can be represented 
by a circuit such as the one  shown in Figure 7. Versions of this basic circuit with more than one 
diode are also popular. 
 
 
Figure 7: Single-diode equivalent circuit. 

21 
 
The current-voltage (I-V) characteristic of this circuit  used to describe PV module performance  is 
described as: 
𝐷𝐷= 𝐷𝐷𝐿𝐿− 𝐷𝐷0 �𝑒𝑒𝑒𝑒𝑒𝑒� 𝑉𝑉+ 𝐷𝐷𝑅𝑅𝑠𝑠
𝑛𝑛𝐷𝐷𝑠𝑠𝑉𝑉𝑇𝑇
� − 1� − 𝑉𝑉+ 𝐷𝐷𝑅𝑅𝑠𝑠
𝑅𝑅𝑠𝑠ℎ
 
where IL is the light-generated current (A), I0 is the diode reverse saturation current (A), R s is the 
module series resistance (Ω), Rsh is the module shunt resistance (Ω), n is the diode ideality factor, 
Ns is the number of cells  in series in the module, and VT is the thermal voltage, 𝑉𝑉𝑇𝑇=
𝑘𝑘𝑇𝑇𝑐𝑐
𝑞𝑞, where k 
is Boltzmann’s constant (1.381x10 -23 J/K) and q  is the elementary charge (1.602x10 -19 C). This 
equation needs five module parameters to solve for current and voltage ( IL, I0, n, Rs, and Rsh). Sev-
eral of these parameters vary with irradiance and temperature.  When these relationships are 
defined mathematically, a module performance model is made (e.g., [19 -20]). The technical man-
uals for such performance models should provide these details. 
2.8.2 Fixed-Point Models 
There are several examples of fixed-point module and system models. These models are limited in 
that they only provide selected points on the I -V curve for a module.  The Sandia Photovoltaic Ar-
ray Performance Model [14] predicts I-V values for five points shown in Figure 8. 
 
Figure 8: Five points determined by the Sandia PV Array Performance Model. 
The Loss Factors Model [21-22] can estimate the maximum power point, Voc and Isc. Other simpler 
models, such as for instance PVWatts  [23], are designed to estimate only the maximum power  
point (Pmpp) and do not resolve the current or voltage separately. 
2.9 DC Wiring and Mismatch Losses 
PV systems usually have a device that controls the operating voltage in order to maximize the 
power delivered from the system.  The voltage is set and controlled by the device (usually an i n-
verter, optimizer, or charge controller), but the actual voltage at the PV cell is altered by the r e-
sistance of the DC cables, which is affected by cable length, cable cross-section, and temperature. 
To obtain maximum power from a PV array , the operating voltage must be controlled by a max i-
mum power point tracking (MPPT) algorithm, which continuously adjusts the voltage and seeks to 
maximize power.  The maximum power voltage (V mpp) varies with irradiance and temperature . 
Usually MPPT is controlled by the inverter for grid -tied systems, or the voltage is controlled by a 

22 
 
charge controller for off- grid, battery-connected applications. MPPT losses can occur when the 
MPPT controller cannot rapidly find the MPP. Typically, these losses are very low (<0.5%). 
DC losses due to resistance in the wiring and interconnections c an lead to current and power 
losses. To minimize these losses , PV designers can connect PV modules in series, thus increasing 
the voltage while keeping the current fixed to the current at maximum power I mpp of a single 
module. Since resistance losses incre ase with the square of the current, this configuration keeps 
these losses low without increasing the costs associated with thicker cables . A consequence of 
connecting modules in series is that any mismatch between the I -V characteristics of the module 
population can lead to mismatch losses.  For example, in a series -connected string of modules, 
since the current flowing through all the modules has to be equal, the module with the lowest 
current will limit the current in the string.  Such mismatch can occur from module inconsistencies 
or from uneven soiling or partial shading.  Module manufacturers bin their modules to minimize 
mismatch and system designers try to avoid string configurations that are affected by partial 
shading. If these situations cannot be easily avoided, system designers can use module scale pow-
er electronics such as microinverters or module -scale DC-DC converters that perform MPPT for 
each module separately, thus avoiding many of the mismatch losses, but at a higher cost. Most PV 
performance modeling applications assume that MPPT and DC losses will be estimated outside 
the software and are entered as system derating factors. 
2.10  DC to AC Conversion Efficiency 
In the case of grid -connected PV systems, the PV array is connected to an inverter to convert DC 
power to AC power. This conversion is associated with losses which depend on the inverter used, 
the operating DC power and AC and DC voltages.  Models to estimate this change in inverter eff i-
ciency are used to estimate these losses. 
Most PV systems are connected to the grid and produce AC power.  One of the inverter’s primary 
functions is to convert DC power to AC power.  This conversion process results in power losses 
that need to be taken into account in the modeling of PV system performance.  These losses are 
expressed in terms of inverter conversion efficiency, which is equal to P AC/PDC. Inverter efficiency 
varies with both DC power level and DC voltage and th is variation depends strongly on the manu-
facturer and inverter design. Figure 9 shows an example of this variation for a typical inverter. 
 
Figure 9: Example of an inverter efficiency profile. 
Inverter performance models aim to represent this complex behavior mathematically.   Models 
are based on measurements made by testing labs that measure efficiency at specific DC power 
and voltage levels. Model parameters are derived from fitting these curves.  The Sandia Photovol-
taic Inverter Performance Model [24] is one such model. 
𝑃𝑃𝐴𝐴𝐴𝐴= �
𝑃𝑃𝐴𝐴𝐴𝐴0
𝐴𝐴−𝐵𝐵− 𝐶𝐶(𝐴𝐴− 𝐵𝐵)� (𝑃𝑃𝐷𝐷𝐴𝐴− 𝐵𝐵) + 𝐶𝐶(𝑃𝑃𝐷𝐷𝐴𝐴− 𝐵𝐵)2, where 

23 
 
𝐴𝐴= 𝑃𝑃𝐷𝐷𝐴𝐴0{1 + 𝐶𝐶1(𝑉𝑉𝐷𝐷𝐴𝐴− 𝑉𝑉𝐷𝐷𝐴𝐴0)}, 
𝐵𝐵= 𝑃𝑃𝑠𝑠0{1 + 𝐶𝐶2(𝑉𝑉𝐷𝐷𝐴𝐴− 𝑉𝑉𝐷𝐷𝐴𝐴0)}, and 
𝐶𝐶= 𝐶𝐶0{1 + 𝐶𝐶3(𝑉𝑉𝐷𝐷𝐴𝐴− 𝑉𝑉𝐷𝐷𝐴𝐴0)}.  
PDC is the DC power (W), V DC is the input voltage (V), V DC0 is the DC voltage level (V) at which the 
AC power rating is achieved at reference conditions, P AC0 is the AC power rating (W) at reference 
conditions, PS0 is the DC power (W) required to start the inver ter process, or self-consumption by 
the inverter. The C1, C2 and C3 parameters are fitting coefficients.  Other inverter models are also 
available (e.g., [25]). 
2.11  AC Wiring and Transformer Losses 
The final step in modeling the performance of a PV system is to account for any AC losses b e-
tween the inverter and the final revenue meter that determines how much AC electricity  is avail-
able. For small systems (e.g., residential) the meter is directly adjacent to the inverter and AC 
losses are negligible.  However, for large systems , it is not un common to have an AC distribution 
system between the inverters and the meter.  Transmission-connected, utility-scale systems may 
have additional transformers.  These wires and transformers will introduce losses to  the system 
output that need to be considered .  A few PV performance models simulate these losses directly 
but many models that are focused primarily on smaller residential and commercial systems simply 
include a derating factor that decreases the AC output by a constant percentage. 
PVsyst includes a simple model for transformer losses [26] that account for:  
• Iron losses due to hysteresis and eddy currents in the core of the transformer, which are 
proportional to grid voltage squared and are usually about 0.1% of the rated power.  
Some systems install a switch to disconnect the transformer from the grid at night to 
avoid these losses when the PV system is not producing power. 
• Ohmic losses within the wire coils of the transformer, which are proportional to I
2R.  
These losses are thus dependent on the system current and are usually several times 
higher than the iron losses on an annual basis. 
Current systems are often more complex than the initial software designs, which were aimed at 
single-inverter designs. In some cases, the software user must either accept the default provided 
by the software, or has to leave the software to determine a loss value to input back into e.g., 
PVsyst. 
24 
 
3 Workshop Presentation Summaries 
Due the increasing popularity of the PVPMC Workshops and a limit of two days for the worksh op, 
a competitive review process was applied  to select a balanced program of high quality present a-
tions.  Interested presenters submitted brief abstracts describing their presentations and the 
workshop organizers reviewed the submissions and built a program of oral and poster present a-
tions. These are summarized in the sections below.  All presentations are available on the PVPMC 
website [1]. 
The workshop started with two introductory presentations by Floria n Reil from TUV Rheinland 
Energy and Joshua S. Stein from Sandia National Laboratories. 
3.1 Session 1: Solar Resource Data and Uncertainty 
This session was chaired by Clifford Hansen from Sandia National Laboratories. 
Table 2: List of presentations and speakers for Session 1. 
Title Presenter Affiliation Country 
Satellite- and Camera -derived 
Irradiance Data for Applications in 
Low Voltage Grids with Large PV 
Shares 
Marion Schroedter -
Homscheidt 
German Aerospace Center  Germany 
Evaluation of Satellite Irradiation 
Data at 200 Sites in Western 
Europe 
Karel De Bra-
bandere 
3E Belgium 
Uncertainty of Satellite Based and 
Ground Based Solar Resource 
Assessment 
Marcel Suri GeoModel Solar s.r.o. Slovakia 
Accuracy of Meteonorm 7.1 Jan Remund Meteotest Switzerland 
Next-Generation Satellite Model-
ing for NREL’s National Solar 
Radiation Data Base (NSRDB) 
Manajit Sengupta National Renewable Energy 
Laboratory 
USA 
Local and Regional PV Power 
Forecasting Based on PV Mea s-
urements, Satellite Data and 
Numerical Weather Predictions 
Elke Lorenz Carl von Ossietzky University 
Oldenburg 
Germany 
Dynamic Uncertainty of Irrad i-
ance Measurements – Illustra-
tions from a Study of 42 Radiom-
eters 
Anton Driesse PV Performance Labs Germany 
Towards an Energy -based Para m-
eter for Photovoltaic Classific a-
tion 
Stefan Winter Physikalisch-Technische 
Bundesanstalt  
Germany 
Timeseries of Spectrally Resolved 
Solar Irradiance Data from Sate l-
lite Measurements 
Annette Hammer Carl von Ossietzky University 
Oldenburg 
Germany 
25 
 
3.1.1 Satellite- and Camera-derived Irradiance Data for Applications in Low Voltage 
Grids with Large PV Shares 
Marion Schroedter- Homscheidt introduced a new satellite -based, open -source solar resource 
product developed by the German Aerospace Center. Data from the Meteosat Second Generation 
meteorological satellite (MSG), which is updated each 15 min (or even 5 minutes in the rapid scan 
mode), is used as input to the Heliosat- 2 and Heliosat -4 algorithms to calculate irradiance at 
ground level. Additional inputs of air quality, global pollution, UV intensity, and aerosols are ob-
tained from the Copernicus Atmosphere Monitoring Service and are used in the calculations. Data 
from these calculations is made available to the public for free.  The project is still under develop-
ment but data is already available for download [26]. 
The talk dealt with satellite- derived irradiance data as the basis to calculate larger solar shares in 
distribution grids. Load flow and voltage are derived from electric ity grid modeling, photovoltaic 
performance modeling and ground-based or satellite-based irradiance observations. 
This paper describes recent results of two European Commission research projects. ENDORSE 
dealt with ‘Energy Downstream Services’ [27] and investigated the use of the European Commis-
sion’s new Copernicus program [28] and its irradiance data as provided in the precursor project 
MACC (Monitoring Atmospheric Composition and Climate [29]).  
CAMS (Copernicus Atmosphere Monitoring Service) provides solar irradiance time series for E u-
rope, Africa, Middle East and parts of South America free for any use. These new services were 
also introduced to the audience. 
 
Figure 10: CAMS webpage for measured sky irradiance product. 
Based on CAMS products, one can also derive cloud physical parameter statistics for each location 
of interest. These can serve as a more detailed information base than only using irradiance time 
series. Irradiance is a parameter that averages out all information about the underlying physical 
processes responsible for the irradiance value. Having insight in to clouds allows more detailed 

26 
 
assessment of a location. The same holds for dust aerosols –  a climatological analysis of dust aer-
osol optical effects was also presented. 
 
Figure 11: Example of cloud and snow statistics for three locations. 
With cloud information being available, nowcasting (forecasting on a <15 min basis)  of the cloud 
cover may be carried out. Algorithms that were developed for large -scale solar thermal conce n-
trating power plants are currently being adapted  for use with photovoltaic generation by distrib-
uted PV plants which are connected to the distribution grid level in a specific region. 
The need for ceilometer-based height assessments of clouds for nowcasting based on sky cameras 
was discussed briefly, as was  the usability of numerical weat her prediction output to achieve the 
same result. 
Finally, an application of CAMS/MACC data usage for PV power monitoring at  the low -voltage 
level was discussed. This is work from the European Commission’s project Orpheus [30] , which 
deals with the hybrid control of smart grids and e.g. the connection of the solar electricity to  the 
heating sector to use surplus solar production. 
The final part of the presentation focused on ideas for applying these data to questions about 
how best to integrate large amounts of PV into the low- voltage power distribution grids. Using an 
example from Ulm, Germany, Marion Schroedter -Homscheidt presented a preliminary study on 
the benefits of satellite-based data for understanding transformer loading from PV systems bac k-
feeding power into the power grid.  Preliminary results showed that transformer loading errors 
were significantly higher when only li mited ground -based sensor data was used.  Errors were 
halved when satellite data was employed.  Finally, she showed some slides on the benefits and 
opportunities for using sky cameras to provide data on cloud height and velocities. 

27 
 
 
Figure 12: Example of applying the satellite irradiance product to a load flow calculation. 
3.1.2 Evaluation of Satellite Irradiation Data at 200 Sites in Western Europe 
Karel De Brabandere presented the results of a study comparing different s atellite irradiance data 
sets to ground irradiance data available in Western Europe. The satellite irradiance data examined 
in the study include: MACC-Rad, HelioClim (v.3, v.4, and v.5), Cpp (KNMI), and GSIP (NOAA). These 
data are derived from both empiric al and physical models.  He focused his validation on hourly, 
daily, and monthly aggregated data from 2011 -2015. Ground measurements were from national 
meteorological stations (160 in France, 12 in Belgium, 31 in the Netherlands).  He used three error 
metrics to compare data: root mean square error, standard deviation of error, and bias error.  
Figure 13 shows an example of the results of the comparison for 2012.  Figure 14 shows similar 
errors for other years.  In summary, errors were generally higher for the shorter time  scales (e.g., 
hourly). The Cpp data and the latest version of HelioClim data displayed the lowest overall errors, 
while the MACC-Rad data displayed the highest bias errors, a fact that was further discussed after 
the presentation in the Q&A session . One possible explanation was that the MACC -Rad data, un-
like the other satellite data, has not been empirically corrected to ground observations.  Despite 
this fact, the MACC-Rad also exhibited a slightly higher standard deviation error as well, especially 
in cloudy weather conditions, which likely reflects real opportu nity for improvements to the algo-
rithms. The HelioClim model showed lower errors with every new version.  GSIP data was only 
available for two months in 2015, but the preliminary results showed it fell in the middle of the 
group in terms of error metrics. 

28 
 
 
Figure 13: Example of error results from the satellite irradiance comparison for 2012. 
 
Figure 14: Example of bias error comparison for 2011-2015. 
3.1.3 Uncertainty of Satellite Based and Ground Based Solar Resource Assessment 
Marcel Suri presented a general overview of the challenges of measuring and modeling irradiance 
at the surface of Earth. He provided a review of historical practices of ground -based and satellite-
based irradiance measurements and discussed the benefits and challenges of these approaches. 
Uncertainties in solar measurements arise from the instrument accuracy and from the deviations 

29 
 
due to instrument maintenance, soiling, calibration drift, changing site conditions, etc.  Thus, only 
highly accurate and well-maintained sensors should be used. Satellite irradiance data is based on 
the satellite and atmospheric data inputs that are updated every 10 to 60 minutes and have rel a-
tively low spatial resolution.  Models used to convert imagery to irradiance are typically semi-
empirical and thus tuned to different geographic regions.  Satellite pixel size and temporal sa m-
pling rates can limit the ability of representing observed variability (for example, microclimat ic 
conditions are difficult to resolve). Uncertainty of the satellite -based models is mostly due to  im-
perfections of the models and the lower resolution of the input satellite and atmospheric data. 
After presenting a thorough overview of irradiance measure ment and modeling issues, Marcel 
then proceeded to present the results of an uncertainty analysis of the SolarGIS solar irradiance 
database. The expected uncertainty for the annual GHI model estimates is comparable to the 
uncertainty of medium -accuracy pyranometers (Figure 15). The uncertainty of low -accuracy and 
less diligently maintained sensors is typically higher than the uncertainty of SolarGIS GHI. The 
model uncertainty of the yearly DNI is lower, compared to well- maintained pyrheliometers and 
RSR instruments (Figure 16). 
The GHI and DNI model uncertainty can be reduced by  site adaptation of the model using at least 
one year of ground measurements. The short-term ground measurements (for a period of at least 
one year) from high -accuracy and well- maintained pyranometers, pyrheliometers and RSR in-
struments are typically used. Table 3Table 3: SolarGIS Uncertainties summarizes yearly uncertain-
ty of the original values of the SolarGIS model, and − for comparison – also the best possible case 
that can be achieved after site adaptation. The uncertainty represents 80% probability of occu r-
rence, based on the analysis of 200+ validation sites worldwide. 
 
Figure 15: SolarGIS GHI uncertainty as a function of averaging time. 
 
Figure 16: SolarGIS DNI uncertainty as a function of averaging time. 

30 
 
Table 3: SolarGIS Uncertainties. 
SolarGIS 
irradiance 
product 
Uncertainty of the yearly 
value computed by the 
original model 
Best achievable uncertainty of the yearly 
value computed by the site-adapted 
model based on more than 3 years of 
high-quality ground measurements 
GHI ±4 to ±8% ±2.5% 
DNI ±8 to ±15% ±3.5% 
 
3.1.4 Accuracy of Meteonorm 7.1 
Jan Remund gave  a short overview of  the accuracy of meteonorm version 7.1  [32], a tool widely 
used for solar radiation assessments either directly as stand -alone software or as plugin in many 
PV simulation tools. Although a standard product, the details of data sources and uncertainties 
are not very well known. 
The largest part of uncertainty is linked to the calculation of long- term averages and is caused 
mainly by the interpolation method. The sources of ground measurements were described briefly 
(mainly GEBA [32]), as well as the methods used to determine the radiation based on the 5 geo-
stationary satellites and the method to mix the two sources. 
A second part handled the observed climatological variations. The uncertainty model used in Me-
teonorm was described, together with  the uncertainty and P10/90 information provided to the 
user. Finally, information was provided on  the additional sources of uncertainty for downst ream 
parameters like hourly global radiation on inclined planes. 
The purpose of the talk was to educate the audience about the data and algorithms used in M e-
teonorm and to give them an overview over the uncertainty levels of the results. 
The three main points of the talk were: 
1. Meteonorm is a combination of a climate database and stochastic weather generator 
and includes both ground measurements and satellite data 
2. Satellite and ground data are mixed to get the optimal results 
3. Uncertainty levels are shown for any location, depend on location and are in the 
range of 2-10% (yearly GHI values, standard deviation). 
The software is updated regularly. In 2017 , time series of satellite data will be accessible within 
Meteonorm. It will then contain not only Typical Meteorological Years (TMYs). 
 
31 
 
 
Figure 17: Geostationary satellites used in Meteonorm Version 7.1 with overlapping areas. Sources 
of satellite data: MT = Meteotest; CMSAF = German Weather Service, MCH = MeteoSwiss. 

32 
 
3.1.5 Next-Generation Satellite Modeling for NREL’s National Solar Radiation Data 
Base  
Manajit Sengupta described a new solar resource dataset that is being developed by the National 
Renewable Energy Laboratory (NREL).  Publicly accessible, high-quality, long-term, satellite-based 
solar resource data is foundational and critical to solar technologies to quantify system output 
predictions and deploy solar energy technologies in grid-tied systems. Solar radiation models have 
been in development for more than three decades. For many years, NREL developed and/or u p-
dated such models through the National Solar Radiation Data Base (NSRDB).  
There are two widely used approaches to derive solar resource data from models: (a) an empirical 
approach that relates ground -based observations to satellite measurements and (b) a physics -
based approach that considers the radiation received at the satellite and creates retrievals to 
estimate clouds and surface radiation ( Figure 18). Although empirical methods have been trad i-
tionally used for computing surface radiation, the advent of faster computing has made opera-
tional physical models viable. 
 
Figure 18: Conceptual data flow for the Physical Solar Model. 
The Physical Solar Model (PSM) developed by NREL in collaboration with the University of Wis-
consin and the National Oceanic and Atmospheric Administration (NOAA) computes global hor i-
zontal irradiance (GHI) using the visible and infrared channel measurements from the Geostatio n-
ary Operational Environmental Satellites (GOES) system. PSM uses a two -stage scheme that first 
retrieves cloud properties and then uses those properties to calculate surface radiation. The cloud 
properties in PSM are generated using the AVHRR Pathfinder Atmospheres -Extended (PATMOS-x) 
algorithms. Using the cloud mask from PATMOS-x, and aerosol optical depth (AOD) and precipita-
ble water vapor (PWV) from ancillary sources, the direct normal irradian ce (DNI) and GHI are 
computed for clear-sky conditions using the REST2 model. For cloud scenes identified by the cloud 
mask, the NREL-developed Fast All-sky Radiation Model for Solar applications (FARMS) is used to 
compute the GHI. The DNI for cloud scenes is then computed using the DISC model (Figure 19).  

33 
 
 
Figure 19: Process models for the Physical Solar Model. 
The current NSRDB update has a 4 -km x 4 -km, 30-minute resolution for the period from  1998 to 
2014. This presentation covered the development of the model and an evaluation of the PSM -
based NSRDB data set compared to ground measurements.  Mean bias errors for seven ground 
stations are shown in Figure 20. 
 
Figure 20: Mean bias errors for the Physical Solar model for seven sites. 
3.1.6 Local and Regional PV Power Forecasting Based on PV Measurements, Satellite 
Data and Numerical Weather Predictions 
Elke Lorenz gave an overview of models for PV power forecasting  and presented  research results 
for a specific forecasting model utilizing  different data sources and methods for PV power predic-
tion for forecast horizons from 15 minutes to several hours. These include the use of PV meas-
urements for very short -term horizons, irradiance forecasts based on cloud motion vectors from 

34 
 
infra-red and visible satellite images for forecasts over several hours, and the combination of data 
from different numerical weather prediction models for forecasts up to several days ahead. The 
different data sources are integrated to form a combined PV power forecasting system using par-
ametric simulation models as well as statistical learning methods. The different approaches we re 
evaluated and compared for single PV plants and for regional PV power feed -in using a large data 
set of PV power measurements. 
Important results: 
• PV power prediction contributes to successful grid integration of more than 38 GWp PV 
power in Germany.  
• Different prediction models are suitable for different forecast horizons: PV power fore-
casts based on satellite data (CMV) are significantly better than NWP-based forecasts up 
to 4 hours ahead. Forecasts based on PV measurements perform best for very short-term 
horizons (e.g., <15 min). 
• A significant improvement compared to single-model forecasts is achieved by combining 
different forecast models, in particular for regional forecasts. 
 
Figure 21: RMSE of forecast PV power versus  forecast horizon in hours for different models: 
Persistence based on measured PV power (orange), cloud motion vector forecast based on 
satellite data (CMV, red), forecasts based on numerical weather predictions (NWP, blue), 
combined forecasts (grey). Abov e: regional forecasts (sum of 921 PV systems distributed in 
Germany), below: single site forecasts. Data set: 921 PV systems in Germany (Monitoring data 
base of Meteocontrol GmbH), 15 minute values, March to November 2013. 
Follow-on work that is planned: 
• Combination of machine learning with PV simulation for integration of additional data 
sources (additional meteorological parameters, additional NWP systems)  
• Probabilistic forecasting: uncertainty information. 
3.1.7 Dynamic Uncertainty of Irradiance Measurements – Illustrations from a Study of 
42 Radiometers 
Anton Driesse introduced the  PVSENSOR project, which is an extensive study of commercial in-
struments designed to measure hemispherical solar irradiance. The overall objective is to develop 
a better understanding of the instrument strengths and weakness, and to apply this information 
strategically to reduce uncertainties in PV system performance analysis.  As the uncertainty of 
irradiance measurement usually far exceeds the uncertainty of electrical power measure ments, 
the potential benefits of this work are significant.  The work is led by PV Performance Labs at 
Fraunhofer ISE in Freiburg and  is carried out in collaboration with the European Joint Research 
Center in Ispra, Italy and Sandia National Laboratories in Albuquerque, New Mexico, USA. 

35 
 
The purpose of the presentation was to share insights gained from the ongoing work and to raise 
awareness of the complexity of uncertainties that are too often hidden behind a single number 
(or forgotten altogether). Indoor testing carried out in winter 2015 primarily at the JRC focused on 
isolating specific characteristics, such as temperature dependenc e, spectral response, dynamic 
response, linearity, directional response. The first phase of outdoor testing took plac e in summer 
2015 with all sensors mounted on a two -axis tracker at Sandia ( Figure 22). They were monitored 
continuously for two months , including several periods in a horizontal position, several periods 
tracking the Sun, and sometimes being involved in  experiments. A period of extended monitoring 
both at Sandia and at PV Performance Labs in Freiburg, Germany during 2016 will complete the 
data collection effort. 
As the instrument collection includes 20 thermopile pyranometers, 10 photodiode pyranometers, 
and 12 PV reference cells, plenty of difference should be expected; but the magnitudes of the 
differences may be surprising. (Figure 23) Part of the spread of the instrument readings seen in 
this graph can be considered to be due to calibration error, which should be constant; the r e-
mainder of the spread can be explained by various n on-ideal instrument characteristics.  The 
presentation used clear -day data segment s from both horizontal and tracking period s to draw 
attention to the clearly visible temperature, angle-of-incidence and spectral effects. 
With the most intensive data collection activities completed, greater effort has shifted to the data 
analysis. This upcoming work involves close comparison of the indoor and outdoor measurements 
to determine the level of agreement between the observations of various individual characteris-
tics. Next, the project will evaluate how well the combination of those individual characteristics 
can explain long-term observations, and how their uncertainties contribute to overall uncertainty 
in the irradiance measurements. 
 
Figure 22: Two sets of sensors mounted on a two-axis tracker at Sandia National Laboratories. 

36 
 
 
Figure 23: Field measurements of glob al horizontal irradiance from 42 calibrated irradiance se n-
sors on a clear day in Albuquerque, New Mexico USA.  The large spread in values represents the 
uncertainty inherent in available radiometers. 
3.1.8 Towards an Energy-based Parameter for Photovoltaic Classification    
Stefan Winter outlined a current effort to develop a new energy -based performance metric for 
comparing different photovoltaic module technologies.  In contrast to standard test conditions 
(STC), which define the power delivered at a specific condition that is rarely achieved in the field , 
this new metric attempts to estimate the energy delivered from a PV module if it were operated  
under a defined set of weather and site conditions.  Thus, differences in the energy rating of vari-
ous PV modules should better reflec t expected energy differences from systems using these 
modules. Furthermore, a focus by module manufacturers on maximizing STC ratings may in fact 
lead to modules that are not optimized for electricity generation  in the field.  For example, in 
some cases lower-efficiency modules at STC may produce more energy when placed in the field. 
The PhotoClass project supported by the European Union is working to develo p such an energy -
based rating standard, which is intended to be implemented as part of IEC 61853 -3. The project is 
organized into five work packages.  WP1 is focused on developing a modeling method for calculat-
ing the energy rating. The approach being developed involves first defining a set of representative 
climatic data sets (8760 hourly values of irradiance, temperature, wind  speed, etc. for certain 
geographic areas). Second, an orientation, tilt angle, and albedo are specified.  Finally, a modeling 
procedure is defined and the energy yield (kWh), the specific module energy rating (kWh/kW
p), 
and a climatically specific energy rating (dimensionless) are calculated (see Figure 25). WP2 focus-
es on definition of required specifications and selection of reference irrad iance devices. WP3 is 
working on standard methods for characterizing irradiance sensors as a function of time, irrad i-
ance, temperature, and angle of incidence. WP4 concentrates  on understanding the characteri s-
tics of the solar resource and simulators. WP5 is an integrating activity to bring together all the 
information gained in the other tasks into an international standard (IEC 61853, parts 1-4). 
Irradiance (W/m2) 
Time of day 
37 
 
 
Figure 24: Flow diagram showing the modeling process being developed for Part 3 of IEC 61853. 
 
3.1.9 PVKLIMA- Time Series of Spectrally Resolved Irradiance Data from Satellite 
Measurements 
Annette Hammer presented an overview of a project aimed at  characterizing and rating the im-
pact of the solar spectrum on the energy yield of thin-film PV modules.  The SOLIS model is used 
with atmospheric input (aerosol optical thickness and water vapor) from the MACC data set in 
combination with a cloud index from satellite images. The method is already available  [33]; the 
quality of the method is shown in Figure 25. 
Open points are the tilt conversion for the different wavelengths and how to handle broken cloud 
situations. 
Optimized treatment of these topics will be developed within the research project PVKLIMA. 

38 
 
 
Figure 25: Diagram showing the methods used to estimate spectral irradiance from satellite data. 
  

39 
 
3.2 Session 2: Spectral Corrections for PV Performance Modeling 
This session was chaired by Alex Panchula from First Solar. 
Table 4: List of presentations and speakers for Session 2. 
Title Presenter Affiliation Country 
Satellite-based Estimates of the 
Influence of Solar Spectrum Var i-
ations on PV Performance 
Thomas Huld Joint Research Centre of the 
European Commission  
Italy 
Combined Air Mass and Precip i-
table Water Spectral Correction 
for PV Modeling 
Mitchell Lee First Solar USA 
Sensitivity Analysis and Unce r-
tainty Evaluation of Simulated 
Clear-Sky Solar Spectra Using 
Monte Carlo Approach  
Giorgio Belluardo EURAC research Italy 
Spectral Corrections for PV Pe r-
formance Modeling  
Fotis Mavromatakis  University of Oregon USA 
Improved Prediction of Site Spe c-
tral Impact 
Benjamin Duck CSIRO Energy Flagship Australia 
Impact of Spectral Irradiance on 
Energy Yield of PV Modules 
Measured in Different Climates 
Markus Schweiger TÜV Rheinland, Solar Energy Germany 
3.2.1 Satellite-based Estimates of the Influence of Solar Spectrum Variations on PV 
Performance 
The presentation by Thomas Huld covered three topics: (1) calculation of the influence of spectral 
variations on PV power, (2) estimates of spectrally resolved solar radiation from satellite data, and 
(3) examples of calculations of these effects for different geographic regions. 
As shown in Figure 6, different PV cell technologies respond differently to light depending on the 
spectrum. To reconcile these differences for the purpose of converting irradiance to current, a 
spectral correction factor can be calculated as: 
𝐶𝐶𝑠𝑠,𝑙𝑙= ∫ 𝑆𝑆𝑆𝑆𝑙𝑙(𝜆𝜆)𝐺𝐺𝜆𝜆𝑠𝑠𝜆𝜆 ∫ 𝐺𝐺𝜆𝜆,𝑆𝑆𝑆𝑆𝐴𝐴𝑠𝑠𝜆𝜆
∫ 𝑆𝑆𝑆𝑆𝑙𝑙(𝜆𝜆)𝐺𝐺𝜆𝜆,𝑆𝑆𝑆𝑆𝐴𝐴𝑠𝑠𝜆𝜆 ∫ 𝐺𝐺𝜆𝜆𝑠𝑠𝜆𝜆 , 
where SRl(λ) is the spectral response at wavelength, λ.  Gλ is the spectral irradiance at wavelength, 
λ, and STC in the subscript indicates the reference spectrum.  The overall spectral mismatch (MM) 
of a PV device over time is then: 
𝑀𝑀𝑀𝑀=
∑ 𝐴𝐴𝑠𝑠,𝑙𝑙𝐺𝐺𝑗𝑗
𝑁𝑁
𝑗𝑗=1
∑ 𝐺𝐺𝑗𝑗𝑁𝑁
𝑗𝑗=1
 , 
where j is the time step of the calculation (e.g., hour). 
To investigate this spectral effect on PV technologies in Europe, Asia, and Africa, spectrally re-
solved irradiance data were calculated using the SPECMAGIC algorithm, developed by Deutscher 
Wetterdienst and the University of Oldenburg.  Cloud effects are c alculated from METEOSAT im-
agers using a Heliosat-type method.  This is then used by SPECMAGIC together with data on aer o-
sols, water vapor and ozone to calculate global and direct irradiance in 24 spectral bands between 
300 nm and 2200 nm.  SPECMAGIC has be en used to process 30 years of METEOSAT data to gen-
40 
 
erate the CMSAF SARAH data set. Hourly global and direct irradiance values are freely available 
through the CM SAF web site:  www.cmsaf.eu.  SARAH version 2 will feature various improv e-
ments and also provide spectrally resolved irradiance data. 
Next, a Module Performance Ratio (MPR) was defined as the ratio of actual module energy output 
to the output if the module always  had the efficiency measured under Standard Test  Conditions 
(Figure 26). 
Figure 27 shows the overall potential for seasonal performance changes in c -Si modules due to 
spectral changes. Relative performance losses can be seen in the Tibetan Plateau of ~5%.  Figure 
28 shows a similar map for CdTe modules. It displays relative energy gains in the tropics, which 
experience high relative humidity.  This effect is discussed in more detail within the next presen-
tation by Mitchell Lee of First Solar. 
 
Figure 26: Map showing the Module Performance Ratio for c-Si modules. 
 

41 
 
Figure 27: Map showing the annual percent change in Module Performance Ratio due to spectral 
effects for c-Si modules. 
 
Figure 28: Map showing the annual percent change in Module Performance Ratio due to spectral 
effects for CdTe modules. 
3.2.2 Combined Air Mass and Precipitable Water Spectral Correction for PV Modeling 
Mitchell Lee of First Solar presented a new spectral correction method for PV modeling. The spec-
tral correction is applicable to both cadmium telluride ( CdTe) and crystalline silicon (c-Si) PV tech-
nologies, and is of simple functional form, which enables it to be easily incorporated into standard 
PV simulation software. The model corrects for changes in spectrum due to air mass and precip i-
table water content. The model has module- specific coefficients based on the module’s quantum 
efficiency (QE) curve. For modules with similar quantum efficiency curves , the same coefficients 
can be used. 
The spectral correction was developed by use of the Simple Model of the Atmospheric Radiative 
Transfer for Sunshine (SMARTS). Spectra were simulated  for varying precipitable water content 
(Pwat) from 0.5 cm to 5.0 cm and absolute air mass (AMa) from 0.8 to 4.75. The range of wav e-
lengths used in calculations was 280 nm to 2800 nm, which are the limits of a typical secondary 
standard pyranometer. All other parameters input into SMARTS were kept at the values from the 
ASTM G 173 standard. Spectral shift (also known as spectral mismatch) was computed for both 
modules at each AMa and Pwat value, using the generated spectra and module QE curves as i n-
puts. The three-dimensional surface depending on spectral shift, precipitable water, and air mass 
was regressed to a simple functional form with module-specific coefficients. The simple functional 
form allo ws the spectral correction to be included into PV simulations tools without running 
SMARTS, or having spectrally resolved irradiance data.  
Publically available meteorological and PV field performance data from NREL [34] was used in 
order to validate the c omputationally derived spectral model. The data was from three locations: 
Cocoa, Florida; Eugene, Oregon; and Golden, Colorado, and it spanned 13 months at each loc a-
tion. Spectral shift was estimated using the ratio of module short circuit current, I sc, to plane-of-
array irradiance, scaled to equal one under standard test conditions. I sc was also corrected for the 
effects of temperature, angle of incidence, and soiling. Data was filtered to remove excessively 
cloudy conditions, low irradiance conditions, an d days with minimal data availability. For the c -Si 
modules, spectral shift was also estimated using an AMa -only method [14] , and for the CdTe 
modules spectral shift was also estimated using a Pwat -only method [35] . Spectral shift derived 
from Isc was irradiance-weighted to daily resolution and plotted against the spectral shift factor as 

42 
 
estimated using the newly proposed model and previously existing models. In all cases, the newly 
proposed Pwat and AMa spectral correction was as good as, or better than, existing simple co r-
rections. 
 
Figure 29: Sensitivity analysis of spectral shift to air mass and precipitable water for a) CdTe PV 
modules and b) multi-Si PV module. 
CdTe 
  
Multi-
Si 
  
Figure 30: a) CdTe spectral correlation proposed by Nelson et al ., [35] versus measured M for the 
CdTe module. b) M estimated using the proposed spectral model versus measured M for the CdTe 
module. c) Spectral correction proposed by King et al ., [14], versus measured M  the multi-Si mod-
ule. d) M estimated using proposed spectral model versus measured M for the multi -Si module. All 
M data is from the Cocoa, Florida test site, of daily resolution, and GHI-weighted. 

43 
 
3.2.3 Sensitivity Analysis and Uncertainty Evaluation of Simulated Clear-Sky Solar 
Spectra Using Monte Carlo Approach 
Giorgio Belluardo of EURAC presented the methodology and research results from the calculation 
of the uncertainty of a Radiative Transfer Model (RTM) using the Monte Carlo technique. RTM are 
used to calculate the spectral and broadband irradiance on Earth’s surface given a set of atmo s-
pheric input parameters. While many research studies exist that evaluate the accuracy of such 
models (i.e. the comparison of RTM -generated spectra with measured spectra) , to the authors’ 
knowledge a research gap still exists in the evaluation of the uncertainty propagation from the 
input parameters to the model output. This is partly explained by the non -integral and not differ-
entiable nature of the Radiative Transfer Equ ation (RTE) implemented in the RTM, that does not 
allow the usual law of propagation of error to be applied. Instead, a statistical approach based on 
the Monte Carlo technique is applied  here. The RTM SDISORT implemented in the UVSPEC tool 
and part of the LibRadtran library is used as the object of the study. The analysis considers the 
spectral range 280 nm -  2500 nm that encompasses the sensitivity of all commercially available 
photovoltaic technologies as well as of spectroradiometers. 
The procedure starts with the definition of a reference set of SDISORT input parameters, of their 
associated error bounds (i.e. the maximum error reasonably attributed to an input quantity), and 
of the Probability Density Function (PDF) of their error. By randomly generating  N>>0 number of 
values for each input quantity according to the defined conditions, it is possible to construct N>>0 
input vectors that are fed into SDISORT. The output spectra are statistically analyzed, and the 
relative uncertainty is calculated for each  wavelength as well as for the broadband irradiance 
(integral of the spectrum). In particular, two options are possible for the generation of the input 
vectors. In the first, only one input parameter at a time varies, in order to evaluate the contrib u-
tion of every single input parameter to the uncertainty of SDISORT. In the second, all input p a-
rameters vary simultaneously, in order to evaluate the combination of error propagation for the 
whole set of input parameters. The overall methodology and the two options described are 
shown in Figure 31. Results of the uncertainty of global horizontal spectr al irradiance generated 
with SDISORT for the reference set of input parameters corresponding to the atmospheric cond i-
tions at Kanzelhöhe Observatory (Austria, 1526 m asl) on April 25th, 2013 at 10 a.m., are shown in 
Figure 32. The input parameters most influencing this spectral uncertainty are: ozone concentra-
tion (especially in the UV -B region), extraterrestrial spectrum (constant contribution considered 
over the whole range), Ångström turbidity coefficient (in the UV -B and UV -A regions) and water 
vapor (in the water absorption bands). 
Next, specific combinations of input parameters corresponding, respectively, to the maximum and 
minimum values of uncertainty of the bro adband global horizontal irradiance generated with 
SDISORT are found. This is done in order to consider all possible combinations of input param e-
ters differing from the reference one used in the previous point, and that can occur at a different 
location and/or at a different time than the reference ones. Results show that the uncertainty of 
global horizontal broadband irradiance simulated with SDISORT and deriving from the simultan e-
ous propagation of uncertainty of all input parameters is between 2.9% and 5 .9%. These values 
are higher, but still comparable to typical uncertainty values of global irradiance measurements 
performed with spectroradiometers. Furthermore, it is demonstrated that the upper uncertainty 
limit would be significantly underestimated if a classic propagation of error was used, because the 
latter does not take the correlation of input parameters into consideration correctly in such a 
case. 
 
44 
 
 
 
 
Figure 31: Schematic diagram of the methodology described, that involves the use of the Monte 
Carlo technique. ( top) Propagation of the uncertainty of one specific input parameter. ( bottom) 
Simultaneous propagation of the uncertainties of all input parameters. 

45 
 
 
Figure 32: Relative uncertainty of the SDISORT output at varying wavelength, due to the uncertain-
ty of each input parameter (colored lines) and to the combined effect of all input parameters 
(black line), for global horizontal irradiance. Conditions correspond to the atmospheric state at  
Kanzelhöhe Observatory (Austria, 1526 m asl) on April 25th, 2013 at 10  a.m.. S: extraterrestrial 
irradiance, o: ozone concentration; w: precipitable water, β: Ångström turbidity coefficient. 
An interesting follow -up of the present study would be to further investigate the propagation of 
the uncertainty from the solar spectrum generated with SDISORT to some PV device calibration 
parameters that are a function of the incident  solar spectrum: the  short-circuit current (I
sc) and 
mismatch factor (MM). Preliminary results on seven different PV technologies show that the u n-
certainty of Isc and MM is higher for technologies with narrower spectral responsivity.  
The work presented in the talk and its po ssible follow-up form an important contribution to the 
clarification of the uncertainty level associated with the estimated solar resource, which is part of 
the PV chain. It is therefore beneficial also for the bankability of solar energy projects. 
3.2.4 Spectral Corrections for PV Performance Modeling 
Fotis Mavromatakis provided an overview to  illustrate that PV performance predictions based on 
using air mass as a proxy for spectral effects can be improved.  The presenter defined a quantity 
he called the average  PV module response, which is nearly identical to the Module Performance 
Ratio described earlier ( 3.2.1). He then showed that this quantity could be calculated using DNI, 
DHI, or GHI irradiance.  Figure 33 shows an example using DNI and normalized to a 45° solar ze n-
ith angle. Other examples using DHI and GHI showed that these effects can differ depending on 
the irradiance source used. 
The talk pointed out a weakness in relying only on air mass as a proxy for spectral effects.   This 
result is consistent with the points made by other presenters in this section. 

46 
 
 
Figure 33: Relative PV module response normalized to 45° solar zenith angle for four different PV 
cell technologies.  
3.2.5 Improved Prediction of Site Spectral Impact 
Benjamin Duck presented a new spectral model for improving the accuracy of PV performance 
modeling. Estimates of the output of deployed PV systems based on pyranometer data are su b-
ject to errors introduced by the mismatch between the pyranometer and PV responses to the 
angular and spectral distribution of irradiance. The importance of applying a spectral correction is 
dependent upon both the timeframe of interest and location/condit ion dependent factors. There 
are two methods most commonly used in literature and incorporated into the most popular PV 
system performance modeling software. The first method uses the air mass function described in 
the Sandia Array Performance Model. This captures the spectral correction as a 4th order pol y-
nomial as a function of geometric air mass only. Coefficients for the polynomial are available from 
Sandia and other sources for all major PV technology types and many manufacturers. The second 
is a model developed by the CREST laboratory at Loughborough University. That model seeks to 
account for the impact of clouds and atmospheric effects by parameterizing the correction as a 
function of both geometric air mass and clearness index. The published CREST m odel only a t-
tempts to treat amorphous silicon devices and is not typically applied to other technologies. 
This talk present ed data showing the application and validation of these two methods against 
measurements at the CSIRO PV Outdoor Research Facility at Newcastle, Australia. The methods 
were compared against photovoltaic device performance normalized  to standard conditions, and 
against direct measurements of the incident solar spectrum. A key weakness demonstrated in 
both methods is the assumption of a u nitary correction factor at a geometric air mass of 1.5. This 
assumption leads to an offset as large as 3.5% between the estimated and measured spectral 
correction that appears to be relatively independent of season. The  authors posit that this offset 
is likely to be linked to the general atmospheric characteristics of the site and hence that it may 
be possible to generate a correction value, which is  termed the site spectral offset. A single p a-

47 
 
rameter air mass function is also shown to be inadequate to acc ount for data collected under 
conditions that do not have completely clear skies. 
The CSIRO team  developed a modification of the CREST method that uses the module spectral 
response and data from the Newcastle site to calculate a spectral correction surface  (Figure 34). 
This surface has been demonstrated to provide an increase in the accuracy of energy yield predic-
tions for the site. The modification is applied by using the spectral response of the module, rather 
than a spectral windowing technique, as the basis for calculating the useful irradiance fraction. 
The result is a value that is equivalent to the spectral mismatch factor. A two -variable polynomial 
surface is then fit to this data using the parameters of air mass and clearness index, where clear-
ness index is derived from solar radiation measurements and using the Haurwitz  model for clear 
sky global horizontal irradiance [36]. The resulting surface for a crystalline silicon module is shown 
below. 
 
Figure 34: Spectral correction surface based on air mass and the clearness index. 
For the Newcastle site, this surface significantly reduces the estimation errors for spectral impact. 
However, it was  noted that there are still some issues with this approach that need to be a d-
dressed: 1) the above analysis has been performed only for data taken from a single location. 
High-quality spectral information from other locations is necessary in o rder to confirm the exis t-

48 
 
ence of any time- independent spectral offset and the structure of the fitting surface ; 2) the pr e-
diction surface is sensitive to the type of clear sky GHI model adopted. Even making small changes 
to the coefficients for the model u sed was shown to affect the surface shape while still providing 
the same predictive improvements. The sensitivity to the GHI model implies that a surface derived 
from one site will not be applicable to another unless the GHI modeling procedure is globally ap-
plicable; 3) dependencies on other parameters are still present within the dataset. In particular, 
changes to the clear sky value for spectral mismatch  have been noted to have different air mass 
dependencies that cannot be explaine d by simple geometric models. A significant correlation has 
been observed with the atmospheric precipitable water content that is also not captured in the 
current model.  
Main points of presentation:  
1. Current models contain an underlying assumption that spectral mismatch = 1 at air 
mass = 1.5. This leads to an offset between estimated and measured data. Further, es-
timation under non-clear sky conditions leads to significant errors in instantaneous 
data as no existing models can reproduce these effects for most conventional PV 
technologies.  
2. A significantly improved spectral impact estimation is possible using an easily imple-
mented modification to the CREST approach that accounts for non-clear sky condi-
tions and incorporates a site spectral offset value. 
3.2.6 Impact of Spectral Irradiance on Energy Yield of PV Modules Measured in Differ-
ent Climates  
Markus Schweiger of TÜV Rheinland  shared the latest results of the national R&D project PV -
KLIMA with regard to spectral irradiance measurements in four different c limates and an analysis 
of the impact on the energy yield delivery in comparison to other environmental effects ( Figure 
35). 
 
Figure 35: Outdoor test installations in Germany, Arizona, India and Italy with 15 PV modules o p-
erating since 2014. 
 
In the first step, the spectral response (SR) of 15 different PV modules was measured in the labor-
atory as shown in Figure 36. The results revealed significant differences in the SR signal of diffe r-
ent technologies and manufacturers. In the second step , the samples were exposed outdoors in 

49 
 
Cologne (Germany), Ancona (Italy), Tempe (Arizona), Chennai (India) and Thuwal (Saudi -Arabia). 
Besides the electrical performance of the PV modules , the spectral irradiance was measured in 
the wavelength range of 300 to 1600 nm in one-minute intervals. Shifts of the solar spectral irra-
diance were analyzed by the average photon energy factor (APE). Given the spectral response and 
the average spectral distribution , gains and losses in the energy yield delivery were calculated 
individually for each sample by the spectral mismatch facto r approach (MMF) according to IEC 
60904-7, as shown in Table 5. 
 
Table 5. Prospective yield gains or losses for different PV module technologies in different climates 
due to spectral effects calculated with the spectral MMF approach. 
Spectral irradiance data measured outdoors revealed a red shift in the distribution of the solar 
spectrum for winter and a blue shift for summer. Also strong daily shifts in the spectral distrib u-
tion could be shown, depending on air mass, cloud coverage and angle of incidence. Spectral e f-
fects almost compensate each other for energy-weighted one-year data of single -junction devic-
es. PV modules with c -Si or CIGS cells did not show a significant dependency on spectral effects. 
By contrast, PV modules with CdTe cell technology are more sensitive to shifts in the spectral irra-
diance and gains in the photocurrent of up to +5.3% were observed at the location Chennai. 
It is planned to continue the outdoor measurements to generate a long -term database for spe c-
tral irradiance data. 
    
Figure 36: Left: Normalized spectral response signal of the tested sample types . Right: Average 
annual spectral distribution of irradiance at 4 test sites in comparison to the AM1.5 spectrum.  
PV Italy Arizona Germany India 
c-Si < 0.5 % > -1.2 % < 1.3 % < 1.6 % 
CIGS < 0.7 % > -1.6 % < 1.8 % < 2.8 % 
CdTe < 1.0 % < 1.1 % < 2.3 % < 5.3 % 
Tandem a -Si (top  
limited) 
< 3.5 % < 7.0 % < 4.0 % < 10.6 % 
50 
 
 
3.3 Session 3: Soiling and Snow, and Other System Derating 
Factors 
This session was chaired by Ulrike Jahn from TÜV Rheinland. 
Table 6: List of presentations and speakers for Session 3. 
Title Presenter Affiliation Country 
Impact of Soiling on PV Module 
Performance for Various Climates 
Werner Herrmann TÜV Rheinland, Solar Energy Germany 
Overview of Sandia’s Soiling Pr o-
gram: Description of Exper i-
mental Methods and Framework 
for a Quantitative Soiling Model 
Bruce H. King Sandia National Laboratories  USA 
Validation of Models for Energy 
Losses due to Snowfall on PV 
Systems 
Janine Freeman National Renewable Ener gy 
Laboratory 
USA 
3.3.1 Impact of Soiling on PV Module Performance for Various Climates 
Werner Herrmann of TÜV Rheinland  presented results of a soiling impact study for PV systems in 
a range of climates in different regions.  During long- term operation of photovoltaic (PV) power 
plants, soiling of the PV module surface can cause significant energy yield losses, which pose a 
particular challenge to PV energy yield prediction. PV soiling loss is dependent on the site charac-
teristics such as climatic conditions or the surrounding environment, but also on the glazing cha r-
acteristics of the PV module. The presentation focused on experimental soiling loss profiles, which 
have been measured at five test locations of TÜV Rheinland, covering a wide range of climatic 
conditions (Figure 37). 
 
Figure 37: Map and table showing the location, climat ic zone, and dates associated with the five 
soiling stations discussed in the presentation. 

51 
 
Dust was monitored by  side-by-side irradiance measurement with two mini- modules, of which 
one was periodically cleaned whereas the other was exposed to natural soiling. The soiling loss 
factor was defined as ratio of effective irradiances reaching the cells. 
Annual PV soiling loss in Tempe (Hot and dry climate) was <4% in the first year of monitoring. Up 
to 15% transmission loss was observed, after which rainfall led to nearly full recovery. Annual 
soiling loss for the tropical test si te is lower (<3%). However , the transmission loss at the end of 
the 3-month dry season was 25%. For temperate climates (Cologne, Ancona) with frequent rain-
fall, annual PV soiling loss is less than 0.5%. For the desert test site in Saudi Arabia, high soiling 
rates were observed (aver age 0.5% transmission loss per day), which indicates that economic 
operation of a PV power plant requires periodic cleaning. 
Dust accumulation on the glass surface changes the angular response of PV modules , resulting in 
significant angular losses. For tes t site Tempe, more than 20% of total soiling loss was caused by 
angular effects. Furthermore, the study clarified that the soiling loss pattern of consecutive years 
can be subject to significant varia tion. Accordingly, long- term monitoring programs are req uired 
for accurate PV performance modeling and energy yield prediction. 
3.3.2 Overview of Sandia’s Soiling Program: Description of Experimental Methods and 
Framework for a Quantitative Soiling Model 
Bruce King of Sandia presented an overview of Sandia’s research program. Sandia has been at the 
forefront of the development of quantitative, repeatable methods to study the impact of soil 
composition and mass loading on the performance of photovoltaic panels since 2012. Their  
methodology includes procedures for formu lating liquid suspensions containing relevant soil 
components, procedures for spray depositing these liquid suspensions onto test panels, and cha r-
acterization methodology to quantify the impact that the resulting coatings have on an underlying 
PV cell. Laboratory work is complemented by three types of soiling stations installed at multiple 
locations across the US to confirm the influence of soil composition on performance and correlate 
to laboratory studies. Two stations, built and deployed by University of Colorado-Boulder, include 
ambient air sampling equipment and glass collection plates to provide better understanding of 
the interrelationship between suspended particulate matter, natural soil deposition rates and 
composition. The third type of station, b uilt and deployed by Arizona State University, monitors 
the impact of soil accumulation on the electrical performance of calibrated PV reference devices. 
The research has enabled Sandia to present a high -level view of the processes that lead to the 
suspension of particulates in the atmosphere and their ultimate impact on PV system perfo r-
mance (Figure 38). 
52 
 
 
Figure 38: Natural processes affecting soiling of PV panels and subsequent power loss. 
 
Combined indoor and outdoor studies have enabled Sandia  to demonstrate that the transmission 
profile of outdoor soiling conditions can be approximated with a laboratory-synthesized analogue. 
Examination of soil composition revealed a few important trends. First, soils containing primarily 
soot and sand provided a neutral response with no impact to the spectrum of the transmitted 
light. Secondly, these formulations were highly susceptible to the soot content.  On a mass basis, 
soot was found to have a 10 -fold impact on transmission loss compared to sand. This finding is 
particularly relevant to PV systems deployed in areas with significant pollution from combustion.  
PV systems near industrial areas or airports may be more susceptible to soiling losses than sy s-
tems located in rural or agricultural areas.  
Likewise, examination of soils containing pigment blends was revealing.  Yellow Goethite rich soils 
displayed greater spectral sensitivity overall, absorbing con siderably in the UV to green wav e-
lengths (~300 – 500 nm), but very little above ~600  nm. In contrast, red hematite- rich soils dis-
played a more neutral absorption.  The greatest impact to transmission loss came from an inte r-
mediate blend of these two, which displayed a strong peak in the UV to green coupled with high 
absorption from 500 – 1200 nm.  
The effect of soiling on angle of incidence response was investigated by applying synthetic (ne u-
tral) soil to one half of a customized split reference cell and measuring Angle of Incidence (AOI) 
response outdoors on a two -axis tracker. A low soiling rate (< 0.5 g/m
2) was observed to have  
minimal effect on the AOI response compared to a reference curve while a high soiling rate 
(>3 g/m2) has a pronounced effect.  This effect is in addition to normal attenuation effects due to 

53 
 
the incidence angle and could be a significant consideration for commercial rooftop systems in 
particular, which are typically deployed at low tilt angles (Figure 39). 
 
Figure 39: Influence of soil on angle of incidence response of PV panels. High soiling leads to 
greater reflection losses than observed on clean panels. This loss is in addition to angle-dependent 
attenuation compared to a normal incidence angle. 
An analysis of tot al suspended particulate concentrations against mass accumulation on glass 
plates collected from outdoor sites revealed a generally linear trend; higher airborne particulate 
concentrations lead to greater  accumulations. Second, both airborne concentration and mass 
accumulation were generally higher at one site in Commerce City, CO.  This area is generally 
known to be a heavily industrial area. Preliminary transmission loss measurements across all sites 
produced a linear response against mass accumulation.  While there was scatter in the data, this 
observation may support a claim that the composition of accumulated soil is rather simple , with-
out a significant spectral component. This claim cannot be verified without compositional analysis 
of the collected soils . However, if it proves to be true could have significant implications for d e-
veloping soil mitigation strategies and for performance modeling. 
3.3.3 Validation of Models for Energy Losses due to Snowfall on PV Systems 
Janine Freeman of NREL presented a very important, yet little discussed, topic: the effect of snow 
on PV systems. The presentation  outlined the importance of modeling snow losses in snowy cl i-
mates, discussed the implementation of such a model in SAM, and most importantly, discussed 
the c apabilities and limitations of the model from the perspective of results gained using it. It 
summarized a full report on the topic that was published by NREL  [37]; more information can be 
found in that report. 
Due to the potential for increased deployment of PV systems in snowy climates, there is interest 
in a method capable of estimating PV losses resulting from snow coverage. A handful of snow 
coverage models have been developed over the last 15 years, but to date, no such models have 
been incorporated in to the PV modeling workflow. With annual energy losses estimated up to 
25% by previous research, there is a clear need for snow losses to be factored into energy esti-
mates for snowy climates. In response to this need, NREL has integrated the methodology of  the 
snow model developed in the paper by Marion et al . [34] into NREL ’s System Advisor Model 
(SAM). The mechanics of Marion’s model can be found in the paper he published on the subject  
[38], but part of the impetus for choosing his model over others is t hat the only additional info r-
mation required from users in order to run the model is a time series of snow depths. 

54 
 
After implementing the snow model in SAM, NREL  performed an initial model validation for two 
systems in snowy climates (Forrestal system in Washington, DC and RSF2 system in Colorado) for 
which they had system specifications, measured performance data, and snow depth data. After 
scaling the output to match the summer months so that the effect of the snow model could be 
analyzed separately from systematic model bias, they  compared the energy predicted by SAM 
with and without the snow model to measured energy, and looked at the results on both an a n-
nual and monthly basis ( Figure 40). These results showed that use of the snow model greatly r e-
duced annual error, but on a monthly basis , it may overpredict the snow loss and make the 
monthly errors worse, as was seen in December for the RSF2 system. This is consistent with Mari-
on’s evaluation of his snow model, and also illustrates the biggest need for future research in this 
topic: improving accuracy at shorter timescales? 
After demonstrating that the model helped to reduce error for two systems, NREL proceeded with 
a national study to model the potential effect of snow on PV systems throughout the continental 
U.S. They modeled two typical fixed-tilt systems (tilt=20° and tilt=latitude) for 239 locations in the 
U.S. using 30 years of historical weather data from the 1961-1990 NSRDB data set. They then took 
the spread of results seen in that study to create a map of general trends in snow losses for the 
continental U.S (see Figure 41). These loss estimations vary as one would expect, reaching over 
20% in the northern regions of the country, and resulting in higher losses for higher elevation sites 
than their nearby neighbors in the region (for example, Flagstaff AZ compared to Phoenix AZ). 
This plot may not capture every year, but is meant to represent typical starting losses for users 
without additional information about their site. 
In summary: 
• The snow loss model implemented in SAM was shown to reduce annual error for two sys-
tems. 
• The snow loss model was used to produce a map of typical snow losses for the continen-
tal U.S. as a starting point for users without more detailed data. 
• Although it reduced error on an annual basis, the model sometimes overpredicted month-
ly or hourly losses. Future work should strive to improve the model at more granular 
timescales. 
 
 
55 
 
 
Figure 40: Results from the validation study using Forrestal system in Washington, DC and the 
RSF2 system in Golden, Colorado. 
 
Figure 41: General trends in average snow losses as a percentage of annual energy production.  
Note: Like-colored regions have similar loss percentages and are labeled in the figure.  The specific 
region around Nevada and the Four Corners i s special (indicated by an *) in that high altitude r e-
gions, such as Flagstaff, Arizona and Ely, Nevada should be considered to be in the next higher tier 
of snow losses. This plot is a broad enough generalization that it may apply to either a tilt = lat i-
tude or a 20° system. 
  

56 
 
3.4 Session 4: Bifacial PV Modeling Challenges 
This session was chaired by Teresa Zhang from SunEdison. 
Table 7: List of presentations and speakers for Session 4 
Title Presenter Affiliation Country 
Introduction to Bifacial Modeling 
Challenges 
Teresa Zhang SunEdison USA 
Simulation and Validation of 
Modeling of Bifacial Photovoltaic 
Modules 
Gianluca Corbellini SUPSI Switzerland 
Realistic Yield Expectations for 
Bifacial PV Systems -  am Assess-
ment of Announced, Predicted 
and Observed Benefits 
Christian Reise Fraunhofer-Institut für Solare 
Energiesysteme ISE 
Germany 
Modeling of the Expected Yearly 
Power Yield on Building Facades 
in Urban Regions by Means of Ray 
Tracing 
Hendrik Holst Institut für Solarene r-
gieforschung GmbH 
Germany 
Multi-Year Study of Bifacial Ene r-
gy Gains Under Various Field 
Conditions 
Jose E. Castillo -
Aguilella 
Prism Solar Technologies, 
Inc. 
USA 
3.4.1 Introduction to Bifacial Modeling Challenges 
Teresa Zhang from SunEdison provided a brief introduction to bifacial module technologies.  This 
technology was first introduced in a U.S. Patent in 1966.  There were multiple presentations made 
on bifacial cell technology at the 1 st European Photovoltaic Solar Energy Conference in 1977.  In 
2000, Russia deployed 10 kW of bifacial PV on the International Space Station.  In 2009, the first 
commercial bifacial modules were released by Sanyo (no Panasonic).  By 2015 more than 100 
patents had been granted for this technology . Tens of MW have been deployed worldwide and 
more than 10 companies are currently offering bifacial module technology in the market.  Mult i-
ple existing cell technologies can be made to be bifacial, including HIT, PERC, and, IBC. 
There are a number of modeling c hallenges facing bifacial technologies.  These include: (1) a lack 
of standards for rating and characterizing bifacial modules and (2) the difficulty in estimating the 
back-surface irradiance resource, which varies spatially and depends on the site charact eristics 
(e.g., albedo) and system design and layout.  Figure 42 shows a selection of deployment options 
for bifacial PV including rooftop, parking structures, tracking systems, and vertical deployments. 
 
57 
 
 
Figure 42: Examples of some of the deployment designs being considered for bifacial PV systems. 
3.4.2 Simulation and Validation of Modeling of Bifacial Photovoltaic Modules 
The purpose of this talk by Gianluca Corbellini about bifacial PV modules  was to describe results 
of experimental research performed at SUPSI, their indoor and outdoor measurement, together 
with modeling of performance. 
For the outdoor measurement, the bifacial output has bee n compared with monofacial modules 
of different technologies (HIT, Poly -Si, CIS, CdTe), during different periods of the year, in Lugano, 
Switzerland (Figure 43). In ad dition to standard sensors ( cell temperatures, front-surface irradia-
tion on the plane of array, global and diffuse horizontal irradiation), dedicated sensors were in-
stalled to measure the irradiation on the back  surface of the bifacial modules. Moreover, a new 
method has been used to estimate the cell temperature of bifacial modules, using open circuit 
voltage, temperature coefficients and irradiation; this model was first validated on a monofacial 
module where the cell temperature was available. 
For the in door measurement, SUPSI tested the reflectance of the dark room for flash testing in 
the case of bifacial modules, in particular measuring the irradiance  seen by back-surface cells; on 
this basis, a new method to normalize the nominal power from  irradiation of both surfaces of the 
bifacial modules has been developed. 
To understand the performance of bifacial module , it is clearly very important to model the co n-
tribution of the back surface, depending on environmental conditions. The new model developed 
within this research accounts for the contribution of the ground -reflected irradiation on the back 
surface and for the diffuse component of irradiation. In contrast to  ray-tracing modeling, this 
study aims to obtain a simple model ( Figure 44 and Figure 45) that can be run very fast but still 
with good results.  
Summarizing the major outcomes of the research in three points: 
• The reflectance of the dark room is needed for indoor testing, to normalize front and back 
efficiency 
• For a single configuration, the simple modeling of irradiation is working well, the tuning of 
the two parameters should be further investigated 
• The gain of bifacial modules with respect to monofacial modules is strongly dependent on 
the position of the Sun in the sky (Figure 46) 
Further research will include: 
• Modeling of the LCOE for bifacial modules: Design of optimal oriented and configured bi-
facial modules (AC/DC ratio, distribution of power curve during the day, self-
consumption) for typical industrial cases and 

58 
 
• Extension of the existing modeling to other orientations and including the dependence of 
the height from the ground and the tilt angle 
 
Figure 43: Test stand with different technologies, including bifacial modules at top left and top 
right 
 
 
 
Figure 44: Modeling of bifacial module performance 

59 
 
 
Figure 45: Five modeling approaches for the back-surface contribution 
 
 
Figure 46: Gain of bifacial modules with respect to monofacial modules (power is normalized by  
front-surface efficiency) 
  

60 
 
3.4.3 Realistic yield expectations for bifacial PV systems – an assessment of an-
nounced, predicted and observed benefits 
Christain Reise of Fraunhofer ISE presented data on realistic expectations of bifacial system pe r-
formance. Bifacial PV modules are able to convert solar irradiation on both surfaces. Therefore, 
larger amounts of generated energy are expected – compared to standard (monofacial) modules. 
Today, bifacial modules are offered by an increasing number of manufacturers, and marketing 
material sometimes promises quite optimistic bifacial gains. 
In fact, bifacial gains are not easy to estimate in advance, as they depend on the spatial distrib u-
tion of the irradiance incident on the rear module surface. Several site and system specific cond i-
tions, such as albedo, module mounting geometry and mounting structure affect this irradiance. 
Currently, none of the widely utilized PV system simulation tools is able to predict the rear surface 
contribution of bifacial modules accurately. 
Fraunhofer ISE’s approach combines simulation tools from different fields of (solar) energy tec h-
nology, the lighting and daylighting domain and the PV system simulation dom ain. In this way, we 
are able to deal with solar geometry, sky radiance distribution, scene geometry, surface prope r-
ties, PV module properties and wiring scheme without any need for severe approximations in the 
model definition. The backward ray -tracing so ftware “Radiance” (Berkeley Lab) is used for the 
optical part of our calculations. Radiance is based on physical relations and physical units of rad i-
ance (W/m
2s) and irradiance (W/m2). The electrical simulations are covered by “Zenit” (Fraunh o-
fer ISE), a detailed software model for all kinds of commercial PV power plants. 
Both tools have been independently validated in several exercises. In this contribution, we report 
on two different validations of the combined procedure. The first set -up deals with the p erfor-
mance of a single bifacial module and uses short -term measurements from a roof test stand at 
Fraunhofer ISE. The second validation uses long -term performance values from a semi-
commercial bifacial PV system monitored by Fraunhofer ISE. 
Now, having this validated tool, bifacial gains are evaluated for a systematic list of system configu-
rations, including single modules, single linear rows and arrays of rows of modules, while looking 
at flat, tilted and vertical mounting options above areas of different albedo. The presented work is 
based on studies prepared for several clients and on in-house research at Fraunhofer ISE for addi-
tional system configurations. 
The configuration results are discussed with respect to their bifacial gain in relation to space  re-
quirements (expressed by ground cover ratios), mounting systems and overall system output. 
Reasonable ranges for expectable gains from bifacial modules and PV systems were given in the 
conclusion of the presentation.  In summary, while results from sing le-module and small -system 
studies have generally shown the possibility of bifacial gains of between 15% to 25%  and even 
higher, larger bifacial systems with multiple rows and self- shading exhibit smaller gains in the 
range of 5% to 15%.   
3.4.4 Modeling of the Expected Yearly Power Yield on Building Façades in Urban Re-
gions by Means of Ray Tracing 
Hendrik Holst presented methods used to simulate annual PV production from BIPV building f a-
çades. While roof-top installations of photovoltaic systems are common these days, installations 
on building façades can provide great advantages, especially in urban regions, where the available 
façade area easily outnumbers the available area on roofs. Unfortunately, not all areas of a build-
ing façade are equally suitable for photovoltaic systems due to shading by neighboring buildings 
or environmental obstacles. This talk presented the results of optical ray -tracing simulations of 
the expected yearly power yield that is incident on  building façades in urban regions and the hi n-
61 
 
terland. These simulations were executed during the study “Vertikale Solar Fassaden in Hann o-
ver” on the behalf of the region of Hannover for LiFE2050. 
First, the authors created a light source representing the yearly average irradiation conditions for 
a location in northern Germany. Our input data are irradiance values, which were measured using 
a pair of photopyranometers at the I nstitute for Solar Energy Research (ISFH) in Hamelin, Germa-
ny over a  period of 14 years (1992 -2006). To allow for a realistic representation of the spectral 
and angular distribution of daylight, they create a daylight model [39-40]. The model includes the 
impact of the S un’s position as well as clouds on the specular and angul ar distribution. However, 
the scattering of light is treated independently of wavelength , therefore neglecting the impact of 
e.g. aerosols or seasonal changes in the atmospheric composition. As a  result of this modeling 
approach, a partition of the celestial hemisphere is created , as shown in Figure 47(a). During the 
simulation, each interval of this partition contains its own spectral distribution.  
 
Figure 47: Utilizing our daylight modeling approach, the celestial hemisphere is partitioned into 
intervals of 5° azimuth and 5° altitude (a). Here, each interval is colored corresponding to the 
mean annual pow er density for the location of Hamelin, Germany. Within the simulation, each 
interval contains its own spectral distribution. A 3D model of buildings is created based upon a 
point cloud (b) obtained from a laser scan of real building facades. 
Using their modular in-house ray-tracing framework DAIDALOS [41]  the authors linked the light 
source with the building models to evaluate the expected yearly power yield that impinges  on a 
building façade. Within the urban hinterland , buildings are typically free -standing houses as 
shown in Figure 48. Under optimum conditions, these buildings can receive yearly solar irradiation 
yields of up to 100 kWh/(m
2 year) on their south orientated façade, being only partially shaded by 
building extensions, e.g. the annex shown in Figure 48(a). This is significantly reduced as soon as 
neighboring buildings (b) or environmental obstacles (c) are considered;  both provide severe 
shading and reduce the expected solar irradiation  yields on the façade by up to 60%. The  simula-
tion times were  kept acceptable in the range of 5 to 15 minutes per simulated b uilding. Within 
the city, buildings typically have more than one floor, providing a large area of façade where ph o-
tovoltaic (PV) systems could be installed. The reduction by other city buildings for irradiation of 
façades is again about 60% of the yield, h owever, as neighbor ing buildings are more common , a 
higher percentage of buildings suffers from this effect. 

62 
 
 
Figure 48: The expected yearly solar irradiation yield incident on the façade of a building in the 
urban hinterland. Under optimum conditions (a) a yearly irradiation yield of about 100 kWh/(m 2 
year) is predicted for the south-facing side of the building. This is reduced by up to 60% as soon as 
obstacles like neighboring buildings (b) or environmental structures (c) are shading the façade. 
 
To conclude, the utilization of a realistic daylight model in conjunction with measured façade data 
allows for a realistic simulation of the expected yearly solar irradiation yield on building facades, 
while the simulation times were  kept acceptable in the range of 5 to 15 minutes per simulated 
building. The results show that PV modules on façades suffer solar irradiation  yield reductions of 
more than 60% if shading from neighboring buildings occurs. 
3.4.5 Multi-Year Study of Bifacial Energy Gains Under Various Field Conditions 
Jose Castillo -Aguilella of Prism Solar present ed multi-year results from deployed bifacial and 
monofacial reference systems in locations in New York and Arizona.  The data showed that con-
ventionally mounted ground bifacial systems have the potential to generate +17.5% additional 
energy compared to  equally rated monofacial systems.  The testing clearly demonstrated that 
additional increased bifacial energy gains can be realized when the surface reflectivity of the 
ground is optimized or when the bifacial modules are used in various vertical configurations.  The 
data suggest that vertically mounted bifacial modules can outperform equally rated, traditionally 
mounted monofacial modules even under adverse ground reflectivity conditions.  These field r e-
sults were compared with Prism Solar’s bifacial energy estimation methods. 
The main goal of the talk was to present field data from bifacial modules under various installa-
tion conditions and show the potential of bifacial modules to increase the kW -h/kW that can be 
obtained from PV system. To this end, both the Prism Solar bifacial and monofacial references 
modules and their electrical characteristics were presented, which were ch osen such that these 
characteristics would be as similar as possible. Since the bifacial energy gain, that is the energy 
being supplied by the rear of a bifacial module, cannot be decoupled directly, the bifacial gain was 
determined by the increased energy  production of the bifacial modules over the monofacial re f-
erence modules mounted under the same conditions.  Seven combinations of test conditions at 
two sites were presented, in which the module height, albedo, and the surface albedo were  var-
ied. An increase in the energy collected by the bifacial modules was reported as each of the vari a-
bles under study increased; depending on the various site conditions, the bifacial gain was b e-
tween 12.31% and 36.8%. 
Additional independent data from the T ÜV/GTM comparative test trial of energy yield was pre-
sented, which further supported the bifacial gains in the 10% -15% for non-optimized bifacial field 
conditions. 

63 
 
 
Figure 49: Bifacial test conditions presented in the presentations 
Field data for vertically mounted bifacial and reference modules under various azimuth conditions 
was also presented with significant bifacial energy gains under all conditions. 
 
Figure 50: Example comparing yields from monofacial (C6SP) and bifacial arrays (B245) 
In addition, t he authorhe discussed what should constitute the true STC and bifacial rating of a 
bifacial module, especially with concerns towards the safety aspect associated with the additional 
currents and power generated by the bifacial modules , since UL/IEC do not  currently address 
these concerns. The shortcomings of not presenting the bifacial ratio or rear- surface STC parame-

64 
 
ters were demonstrated with an example and how the lack of standard test conditions during 
flash testing (white/black background, collimation, etc.) can cause major differences in the STC 
rating of bifacial modules.  In terms of safety, the TÜV/Prism BSTC rating was presented; this rat-
ing uses calculated front and rear surface performance parameters that take into account STC test 
conditions with 1000 W/m2 on the front of the module and 300  W/m2 on the rear of the module 
to account for the additional power of the bifacial module. 
Future Work: 
• More data sites and cooperation with entities such as Sandia National Labs and NREL to 
improve the available data sets and knowledge base. 
The most important aspects of the talk: 
• Bifacial modules can significantly increase the kWh/kW yield of PV systems when they are 
installed in conditions that take advantage of their inherent ability to generate more en-
ergy from the additional energy reaching the rear of the module. 
• The bifacial gain of bifacial modules is influenced by three main variables: height, tilt, and 
surface albedo. The maximum bifacial gain is reached in applications such as vertical tilts 
with the module oriented in an east/west configuration, or in high tilt conditions (+20 de-
grees) with high surface albedo. 
• The lack of current bifacial standards makes the comparison of one manufacturer with 
another difficult. In addition, the current standards (IEC, UL/ Q+) fail to take into account 
the additional current/power that could be produced by bifacial modules, which may 
prove to be a safety issue. 
 
 
65 
 
3.5 Session 5: PV Modeling Applications: Modeling Tool Updates 
This session was chaired by Jeffrey Newmiller from DNV GL. 
Table 8: List of presentations and speakers for Session 5 
Title Presenter Affiliation Country 
Latest Features of PVsyst Bruno Wittmer PVsyst Switzerland 
pvSpot - PV Simulation Tool for 
Operational PV Projects 
Tomas Cebecauer GeoModel Solar s.r.o. Slovakia 
Recent and Planned Improv e-
ments to the System Advisor 
Model (SAM) 
Aron P. Dobos National Renewable Energy 
Laboratory 
USA 
Helioscope Paul Gibbs Folsom Labs USA 
Performance Modeling of PV 
Systems in a Virtual Environment 
Angele Reinders University of Twente Netherlands 
 
3.5.1 Latest Features of PVsyst 
Bruno Wittman of PVsyst presented an overview of new and upcoming features of the PVsyst 
software for the simulation of PV installations. 
The features covered have been  introduced into PVsyst since May 2014, which was the date of 
the last presentation of this kind at a Sandia PVPMC workshop. 
At the time of the presentation, the current version of PVsyst was 6.39. 
New features in V 6.39 
1. Meteorological Input 
The built-in meteorological database of PVsyst was updated from Meteonorm 6.1 to Meteonorm 
7.1. This new version has a larger underlying set of measurements covering a longer time  span. It 
also uses an improved interpolation algorithm to calculate the clim ate at locations between 
measurement stations. 
A tool was added to PVsyst that allows direct comparison of yearly meteorological input files. This 
comparison is useful to analyze the climate over several years, evaluate different data sources or 
compare the climate at different sites. It can be used to estimate the parameters needed for a 
meaningful P50/P90 analysis. 
Furthermore, there is now the possibility to generate hourly meteorological input files based on a 
clear sky model. This allows a very easy cross-check of monitoring data against the simulation 
results on cloudless days, without having to actually measure the irradiance. 
2. Extended System Definitions 
It is now possible to make simulations of systems that make use of power optimizers. Models of 
SolarEdge, AMPT and TIGO are supported. The optimizers are associated to the module types in 
the simulation, and their specific configuration can be defined in detail. 
66 
 
Inverters with several MPPT inputs can now be configured in a more flexible way. Previou sly, the 
distribution of the total nominal inverter power was assumed to be equal among all inputs. It is 
now possible to attribute specific fractions of the total power to each individual MPPT input. 
3. 3D Editor  
Several improvements have been made to the editing of 3D scenes (figure 1). 
In the 3D editor , it is now possible to define groups of objects and edit their common properties 
at once.  
The ground objects describing the topology, which previously  could only be imported from exte r-
nal files, can now be edited directly in PVsyst. 
Arbitrary polygonal filling zones can be defined. A filling algorithm populates the zones with PV 
tables according to configurable rules. 
Up to now, the importing of scenes from the Helios3D software only recover ed the sensitive PV 
tables. Now, also other shading objects are included and are imported into the PVsyst scene. 
4. Batch Simulations 
The list of parameters that can be changed in batch simulations increased significantly. Around 40 
different parameters are available covering meteorological input, orientation of the panels, shad-
ing details, system configuration, module properties and different losses. 
5. Optimization Scans 
A new tool was added to simplify the creation of parametric scans. It is a simplified batch mode 
that integrates all steps from the creation of the parameter ranges through the execution of the 
simulations and finishing with the visualization of the results (figure 2). The available simulation 
parameters for this tool are tilt angle  and azimuth of the PV panels, and the result variables that 
can be visualized are i ncident irradiance, PV power and power injected into the grid. The lists of 
simulation parameters and result variables will be expanded in the future. 
6. Other Tools 
A new tool has been added to make a simple calculation of the carbon dioxide balance. The calcu-
lation is based on life cycle emissions (LCE) and can either be used easily with reasonable default 
values, or configured in great detail by the user. 
A dialog has been added with a  tool to study the behavior of the Incident Angle Modifier (IAM). 
The IAM describes the angular changes of the reflectance of the module surface. Different models 
are proposed for this description, including fully customized IAM curves. The effect on direc t, 
diffuse and albedo irradiance can be visualized and the impact on the annual yield of the produ c-
tion of each of these components is estimated. 
Upcoming features for V6.40 and higher 
1. Text-based file format 
The format of the PVsyst files describing the  PV system, its components and the results will 
change from binary to a text-based format. The purpose of this change is to increase compatibility 
between different PVsyst versions. 
2. 3D editor and shading calculation 
67 
 
The algorithm to compute shading loss es will be revised to increase the speed of calculation. The 
3D editor will be based on the OpenGL library to allow faster rendering and a more fluid work 
flow, especially on scenes that are large or have a lot of details. 
It will be possible to add background pictures to the 3D editor. These can be either photographs 
of the terrain or technical drawings. A set of drawing tools will allow a quick creation of 3D objects 
on top of the pictures, making it easier to create the 3D scene. 
3. Battery-Based Systems 
The simulation of battery -based system is being re vised to harmonize it with the grid -connected 
approach in PVsyst. Tools are being added to visualize the behavior of the battery controller, in 
order to obtain the optimal working thresholds quickly. 
Li-ion batteries and controllers will be included in the system definitions.  
On the long term , the simulation of hybrid systems will be possible (grid -connected with local 
storage). 
 
Figure 51: New features for the PVsyst 3D editor Version 6.39. 
 

68 
 
Figure 52: Tool for creating and visualizing parametric scans in PVsyst. 
3.5.2 pvSpot - PV Simulation Tool for Operational PV Projects 
Tomas Cebecauer of SolarGIS presented a new PV performance modeling capability called pvSpot 
that was developed by SolarGIS to offer PV performance estimates based on their worldwide irra-
diance database project, Solar GIS.  pvSpot combines their irradiance data set with meteorological 
data, and terrain data to allow detailed performance models to be run and compared against 
monitoring data collected from operating systems.  Systematic differences in these values may be 
useful in identifying performance issues with the system. The PV pe rformance model approach is 
shown in Figure 53. 
 
Figure 53: Details of pvSpot’s approach to PV performance modeling. 
This same modeling appr oach is also being applied to forecasting the future production of PV 
plants for more efficient participation in the energy market as well as longer -term forecasts that 
are used for financing of projects. 
The model can be accessed as a web service or resul ts can be automatically delivered via FTP and 
can be automated to track and forecast the performance of a fleet of as many as thousands of PV 
plants.  Figure 54 shows a comparison of a single plant’s performance to the expected perfo r-
mance predicted by the model for 15-minute time intervals.  It illustrates the model’s very low 
bias error.  The prese ntation also showed several examples of the model’s ability to detect per-
formance problems including snow losses, string failure, shading, and inverter clipping. 

69 
 
 
Figure 54: Comparison of expected production to measured production shows a low bias error. 
3.5.3 Recent and Planned Improvements to the System Advisor Model (SAM) 
Aron Dobos from NREL reviewed  recent improvements to the System Advisor Model (SAM) for 
techno-economic modeling of photovoltaic systems.  
The new battery model in S AM is designed for behind -the-meter analysis with complex utility 
tariff structures to help assess the economic viability of battery storage systems in conjunction 
with PV systems. The model considers lithium-ion and lead-acid technologies, and includes a flex-
ible, manually scheduled dispatch controller along with several automatic dispatch strategies.  In 
lifetime analysis mode, the effects of battery cycling and degradation are accounted for including 
the costs of replacement. The battery model was validated against laboratory measured test data 
for two different system types (Figure 55). 
PV simulations can be run for up to 30 years at sub -hourly time steps. This new simulation mode 
allows detailed analysis of system DC/AC size ratio options with module degradation (Figure 56). 
The new integrated 3D obstruction shading loss mo del in SAM is a simple -to-use tool for calculat-
ing beam and diffuse shading losses  (Figure 57). The tool can underlay 2D aerial imagery, and 
future versions will inclu de an option to estimate non -linear energy losses in systems with paral-
lel-connected shaded strings. 
Future work on SAM includes the addition of a plane-of-array (POA) irradiance input option for PV 
models, new automatic energy storage dispatch strategies,  support for multiple input MPPT i n-
verters, transient PV thermal models, 3D shade model validation and intercomparison, and i m-
provements to spectral response models. 

70 
 
 
Figure 55: Example of modeling results from the System Advisor Model (SAM) for a PV -battery 
system. 
 
Figure 56: The output summary screen in the System Advisor Model (SAM). 

71 
 
 
Figure 57: The 3-D interface Shade Calculator in the System Advisor Model (SAM). 
 
Figure 58: Shading objects can be drawn based on satellite imagery to capture the position of 
trees. 
3.5.4 Helioscope 
Paul Gibbs from Folsom Labs gave a live demonstration of the Helioscope modeling software.   
This web-hosted software aims to closely integrate the PV system design process with the optim i-
zation of PV performance.  The user starts with a satellite image of the site and then uses basic 
drawing tools to layout the area of the PV array, which is lo cated either on a rooftop or the 
ground.  The next step is to choose the PV modules, type of racking, and inverters.  Many i m-
portant engineering constraints can be added to the design, such as minimum offsets from the 
roof edge.  The program can also calcu late and help avoid shading losses based on a Google 

72 
 
SketchUp model of the site.  Once the components and constraints are defined, the software a u-
tomatically designs the system, creating, on the fly, a bill of materials, including the wiring sched-
ule.  Inv erters can be easily moved and stringing can be adjusted to minimize losses and wire 
needs.  The performance model engine is compatible with PVsyst and accepts .PAN files as input. 
3.5.5 Performance Modeling of PV Systems in a Virtual Environment 
Angele Reinders presented on a new approach to PV performance modeling using virtual reality 
technologies.  Virtual reality applications use sophisticated graphics engines to simulate a scene 
on a computer display. In order to make these simulations appear realistic to the human eye, they 
must be able to represent how light interacts with the objects in the scene.  This talk describes 
research being done at the University of Twente to utilize such tools to simulate the light available 
to a PV system in a virtual environmen t. The advantage of using such a method is  that it is easily 
capable of representing quite complex geometries while also being optimized for speed and m o-
bile objects. For example, conventional PV performance models are not at all designed for use in 
designing mobile PV such as electric cars or boats. Because the virtual reality engines are designed 
to work with dynamic, high -speed video games, they can easily be used to simulate the light 
available to a mobile PV system. 
The tool built at the University of Twente is called VR4PV and it is developed using Quest3D Virtu-
al Reality Software.  The simulations use rasterization techniques rather than ray tracing, which 
needs large computational resources. PV sub-models included in VR4PV include the solar position 
(Blanco-Muriel), solar decomposition (Orgill-Hollands), transposition (Liu-Jordan), PV temperature 
models (Skoplaki, Ross, King, and Veldhuis), and single-diode equivalent circuit models. 
Validation of the model has been performed. Relative errors in the tilted irradiance was evaluated 
at four sites and shown to be <5%. 
An example of a simulation was shown that considered four PV cells located on an outdoor solar 
light fixture with complex shade patterns ( Figure 59). Each cell experiences a different irradiance 
pattern over time. The model was then run using inputs shown in Figure 60. The resulting output 
power from each cell is shown at the bottom of the figure.  This type of simulation would be i m-
possible using existing conventional PV simulations programs designed for g round or roof mount-
ed systems. 
As PV systems become less expensive and they are installed in  more complex environments, new 
simulation tools will be needed to help support designs and deployments. VR4PV is an example of 
the type of tool that may prove very useful for such work. 
73 
 
 
Figure 59: Position of solar cells on a street light used as an example. 
 
 
Figure 60: Examples of results of the VR4PV model. 

74 
 
3.6 Session 6: Field Monitoring and Validation of PV Performance 
Models 
This session was chaired by Werner Knaupp from PV-plan. 
Table 9: List of presentations and speakers for Session 6 
Title Presenter Affiliation Country 
High-Speed Monitoring of Mult i-
ple Grid-Tied PV Array Configur a-
tions 
Matthew Boyd National Institute of Stan d-
ards and Technology 
USA 
Field Data from Different Cl i-
mates for the Validation of Mod-
ule Performance Models 
Gabi Friesen SUPSI Switzerland 
Comparison and Validation of PV 
System and Irradiance Models 
Benjamin Matthiss Zentrum für Sonnenenergie - 
und Wasserstoff -Forschung 
Baden-Württemberg 
Germany 
The “best” PV Model Depends on 
the Reason for Modeling 
Steve Ransome  SRCL UK UK 
Using Advanced PV and BoS 
Modeling and Algorithms to O p-
timize the Performance of Large 
Scale Utility Applications 
Jürgen Sutterlueti Gantner Instruments (GI) Austria 
System Performance and Degr a-
dation Analysis of Different PV 
Technologies 
Yuzuru Ueda Tokyo University of Science Japan 
 
3.6.1 High-Speed Monitoring of Multiple Grid-Tied PV Array Configurations 
Matthew Boyd presented an overview of high -speed and resolution PV monitoring being done at 
the National Institute of Standards (NIST) in the USA. Three 73 kW to 271 kW mono -Si grid -
connected arrays installed in different orientations and configurations have been monitored since 
August 2014 with research -grade instrumentation that is sampled and saved every 1 second. A 
local weather station was also constructed with redundant measurements of all main meteor o-
logical and solar components in addition to the full solar spectrum, UV, IR, and I -V traced refe r-
ence modules in the same orientation as the arrays. Data availability for all systems is currently at 
99 %. Cameras are also deployed at each array and weather station, taking high -resolution pic-
tures of the shading and snow cover every 5 minutes as well as images of the full sky every 8 se c-
onds. 
Follow-up work underway includes setting up a public data portal for the data  sets, and using the 
data sets to validate short -term irradiance fore casting and inverter/grid interaction models as 
well as examining dynamic electrical effects from irradiance enhancements and transitions. Mo d-
elers or analysts interested in using any of the data before the public data portal is available can 
contact Matthew Boyd at matthew.boyd@nist.gov . 
75 
 
 
Figure 61: A selection of the irradiance and electrical measuring instruments and sample images 
from the cameras installed at one of the PV arrays. 
 
Figure 62: The weather station, showing the various stationary and sun- tracking instruments as 
well as the I-V traced reference modules. 
3.6.2 Field Data from Different Climates for the Validation of Module Performance 
Models 
Gabi Friesen of SUPSI gave an overview of external parameters which can influence module ener-
gy yield measurements and benchmarking studies under different climates. At present, the lack of 
standardized guidelines for perform ing module yield measurements and analyses leads to mi s-
leading data being reported to the end  user. It is emphasized that to better understand techn o-

76 
 
logical differences, reliable, accurate and comparable measurements are needed. Large  discrep-
ancies in measurement practice, uncertainty declarations and reporting can easily lead to contr a-
dictory results. For example, m odules ranked as the ‘best’ in one study come out as ‘average’ in 
another study. Unfortunately, field data are often reported without any measurement uncertai n-
ty, which makes the validation of models very difficult. The presentation raised the question as to 
what is needed to improve the comparability of data measured outdoors under different climatic 
conditions (see Figure 63). 
 
Figure 63: Field testing requirements and contributions to uncertainty in outdoor PV module yield 
measurements. 
An example of typical measurement uncertainties for each contributing factor is given for abs o-
lute PR measurements and  relative measurements (rankings)  in Figure 63. The presentation di s-
cussed not only how the final measurement uncertainty is affected by the hardware specific a-
tions, but also by the experimental design, the sampling of modules, the test stand configuration, 
the operation and maintenance practice, the power rating, the irradiance measurement and last 
but not least , the data processing approach and quality control. In ra nkings, many of the unce r-
tainties can be reduced or totally neglected. The harmonization of measurement practice helps in 
reducing the uncertainty  contributions. Power rating remains however one of the major unce r-
tainties and has to be approached separately. 
At the end of the presentation, the IEA Task 13 activities of S ubtask 3.2 were presented and p o-
tentially interested parties were invited to participate actively in the definition of a future guid e-
line and the set-up of an open-source reference data base that aims to achieve better comparabil-
ity of data with clear measurement uncertainties, better validation studies and models , and 
greater confidence in technology benchmarking. A standardized method for the assessment of 
field measurement uncertainties and the reporting of results is part of this. 
3.6.3 Comparison and Validation of PV System and Irradiance Models 
Benjamin Matthiss of the Zentrum für Sonnenenergie und Wasserstoff -Forschung in Baden -
Württemberg presented on an  approach for yield and self- consumption estimation in Germany . 
The goal was to estimate the total PV generation in Germany based on information about the 
installed capacity and location in combination with satellite irradiation data. 
In a first step , various irradiation models were compared and validated to analyze their accuracy. 
Therefore, the tilted plane irradiation output of 6 irradiation models (Perez, Klucher, Hay&Davies, 
Isotrop, King, Reindl) were compared with high -resolution measurement data for a irradiation on 
a 40° tilted , south-facing plane. Best results were obtained with the Perez model for the given 

77 
 
location in southern Germany. Furthermore , the PV and inverter model were validated with 
measurement data. 
For the ZIPcode -based Solar Power c alculation (ZIPSoP), each zip code area was modeled with a 
distribution of PV  system orientations. The size and approximate location of the PV  system was 
known from a data  base of the federal power grid  agency. Unknown was the orientation, the PV  
technology and the inverter type.  
The yearly yield was known f or a subset of PV  plants. This data was used to optimize various 
model parameters ( temperature coefficient, orientation distribution, efficiency, scaling factor, 
minimum incident angle) with a non -linear optimization method, as shown in the figure below. 
The main problem with this approach was an overfitting with respect to the training year. Add i-
tionally, the input data set contained various obvious errors and inaccuracies which caused pro b-
lems with the proper estimation of the coefficients. The accuracy reached with this version was 
between 1% and 10% depending on the training and validation year. With an older model of the 
ZIPSoP tool, accuracies between 3%-4% were achieved. The accuracy for a valid estimation of self-
consumption in Germany should be constantly below 1%.  
The three main points and results of the talk were: 
• The Perez Model performed best in the irradiation model comparison for Germany.  
• Yield estimation accuracy for Germany with the currently best performing yield prediction 
model is about 3%-4%. 
• For the quality of the estimation, the input data has a key role. 
 
Figure 64: Data flow model showing how validation and comparison were performed. 
3.6.4 The “best” PV Model Depends on the Reason for Modeling 
Steve Ransome of SRCL presented an overview of criteria used to choose the best PV performance 
model for a given application.  PV Performance Models should deliver unbiased performance u n-
derstanding and prediction with best accuracy for optimized project assessments and reduced risk 
for the asset owner. Therefore, the appropriate model should be utilized. 
The performance of PV modules/arrays in outdoor weather conditions can be modeled for  many 
different reasons including: 
1) Production process optimization (to minimize losses at Standard Test Condi-
tions). 
2) Determination of coefficients e.g. “PMAX vs. TMODULE”, “Efficiency vs. Irra-
diance” etc. 

78 
 
3) Overall system energy yield predictions vs. simulated weather inputs. 
4) Benchmarking different PV technologies (vs. differing PMAX, Low Light etc. 
coefficients). 
5) Validation of instantaneous performance (to prove the module or array is 
working correctly). 
6) Fault finding (if under-performing) – which model parameters are responsi-
ble? 
7) System output validation e.g. kWh/ year. 
8) Degradation rate vs. time, which parameters are degrading and at what rates? 
PV Performance models derive their coefficients from IV curves taken at different irradiance  val-
ues and temperatures, fitting either the entire IV curve (e.g. 1 -Diode), a selection of points and 
gradients (e.g. Loss Factors Model and SAPM) or just modeling the maximum power point (e.g. 
Matrix method) as shown in Figure 65. 
 
Figure 65: “Full IV curve” (green), Fitted “points and gradients” (purple), “PMAX only” (red), te m-
perature coefficients (in brackets). 
The ability of several models to differentiate the performance from IV curves over a range of 
technologies measured by NREL and Gantner Instruments outdoor was analyzed. 
The performance of a good c -Si module, a good thin-film module and a poor  thin-film module 
(with poor RSC and ROC) measured by NREL has been analyzed with all three models. The relative 
energy yield for Colorado is compared as an example.  
These models are being studied as preparation for incorporation  into Gantner Instruments’ Web 
Portal software for optimum performance modeling  and understanding. Figure 66 shows how 
data from measured IV curves at different irradiance values and temperatures (top left) appear as 
parameters in a 1 -diode model (top right), “points and gradients” model such as the  loss factors 
model (LFM) (bottom right) and Matrix Method (bottom left). 

79 
 
 
 
Figure 66: Processing sequence from IV curves vs. GI and TMOD to the three model types. 
The 1-diode model was hard to analyze  to identify the differences between the module types as 
some of the parameters were not monotonic (and thus were hard to fit), their magnitudes were 
very different (e.g. 10 -10 to 103) and there was some difficulty in fitting (e.g. the ideality factor – 
green in Figure 66 and saturation current – grey in Figure 66 can compensate each other and a p-
pear as saw tooth shapes). 
The Matrix method had less detail , as each temperature- irradiance bin was just an average of 
different values, so it was hard to see what the overall efficiency shape was , as it could have 
spikes due to bad data points. It could be characterized  by the maximum efficiency and its loc a-
tion (irradiance and module temperature of the peak) plus the fall- off rates at both high 
(*I2.RSERIES) and low irradiance (LLEC) and also high temperature (Gamma). 
The LFM was much easier to analyze for the differences in performance. An ideal module should 
have all parameters with a constant value with irradiance with values of 1 and this was near for 
the best c -Si module. The CdTe module shown in figure 2 is limited by poor nRoc (pink) at high 
irradiance which is caused by high RSERIES. The poorly performing thin-film module was shown to 
be limited also by poor nRSC at low irradiance which is due to a fall in RSHUNT. 
Recommendations 
• Normalize data to ensure easier understanding (e.g. ISC.MEAS/ISC.STC/GI). 
• Use physically significant coefficients (e.g. nVOC: normalized VOC) rather than just poly-
nomial fit coefficients. 
• Ensure IV scans are of good quality, calibrated and plausible with little scatter. 
• For simple kWh/kWp calculations at optimum sites the efficiency-only model may be 
enough. 
• For a fast inline check, studying degradation/ non-optimum performance, a 
“points+gradients” model is better. 
• For ultimate understanding, the full weighted point IV curves should be studied. 
Needs for optimum modeling: 
• To be able to differentiate “offsets between technologies” from “product variability with-
in a type”. 
• To obtain curves that are easy to fit and recreate these curves with simple models. 
• To quantify performance loss or optimization possible from sub-standard modules. 

80 
 
 
Future work 
More data will be studied from the NREL dataset and also Gantner Instruments measure ments. 
The models will be compared with a one-year data series residual analysis to show which ones fit 
modules under varying conditions best (i.e. not just a kWh/kWp measured vs. predicted value) 
3.6.5 Using Advanced PV and BoS Modeling and Algorithms to Optimize the Perfor-
mance of Large Scale Utility Applications 
Jürgen Sutterlueti from Gantner Instruments presented an overview of their approach to PV sy s-
tem monitoring and introduced their Web -Portal application.  When monitoring utility scale PV 
projects, some questions are commonly asked about the needs and benefits for investment. Here 
are some key requirements for understanding and implementation:  
Performance understanding 
In order to be able to do solid analysis and interpretation , one has to have a good understanding 
of PV performance.  
Gantner Instruments has had its own research test site in Arizona, USA with data since 2010 as 
shown in Figure 67.  
The aim of this Outdoor Test Facility (OTF) is to provide investors, EPCs and asset owners with 
recommendations on what parameters and methods they should be using to ensure their utility -
scale solar projects achieve their full financial and energy yield potential. 
 
Figure 67: Gantner’s OTF in Arizona, USA. 
 

81 
 
Key benefits from Gantner’s OTF: 
• PV Module performance track record since 2010 
• Baseline for next generation of PV modeling and prediction of PV plant performance and 
monitoring 
• Technology benchmark  
• Bankability support for EPCs, Investors, Insurance 
• Key for improved utility PV monitoring concepts  
• Effective and repeatable analysis based on the LFM 
Data from the OTF is analyzed with the LFM [21].  
Data acquisition and handling 
Market expectations: Figure 68 illustrates a monitoring and control concept for cost -effective PV 
electricity generation and risk reduction used at Gantner Instruments. 
Requirements:  
• Multiple import data streams, standardized 
• Fast check to validate all measurements sensors, inverters, strings etc. – first as plausible, 
then good. 
• Automated checks (real time), constant performance 
• Regular sanity checks 
• PV power plant structure to identify losses 
• Normalization of data sets for quick comparisons 
• Good sanity check for all components (easier with normalized data)  
• Redundant measurements of weather and electrical variables.   
• Availability monitoring: For each component (inverter, system, sub-system, production 
batch, … ) to support preventive maintenance strategies 
82 
 
 
Figure 68: Process overview of the Gantner web portal. 
Data Analysis 
When it comes to data analysis, data consistency is key. Thus, the following steps are reco m-
mended: 
• Perform real-time sanity checks for physically meaningful values 
• Make uptime tracking / availability audits 
• Provide overall sensor reviews for measurement validity 
• Monitor irradiation sensor drift 
Parameters and graphs should be shown with these aims:  
1) Simplification of what is relevant in terms of $ (money) and kWh (energy)  
2) Determining potential short, midterm impact,  
3) Preventive maintenance 
Performance prediction and optimization 
Set up algorithms to predict instantaneous PV and BoS performance for measurement validity and 
energy yield predictions. The b asic version already gives very useful results for system cross -
checking and trend detection (soiling alerts, shading, … ) which is very helpful fo r real-time error 
detection.  
Investment vs. Benefit of Monitoring: Impact on system cost (CAPEX), O&M (OPEX) and LCoE 
The case study shown in Figure 69 is a system in Europe (10MWp AC) which includes a monitoring 
cost share of the system price:  

83 
 
~ 1.4% (0.013€/Wp, EU); this CAPEX of installed monitoring gives direct control of 17% of the LCoE 
Cost (O&M cost) and controls the performance of the inverter, cables and connections, …  
The comparison with no  monitoring vs. a PV power plant with monitoring shows that the mon i-
tored plant can deliver a 7.3% better energy yield, resulting in a 4.5% better LCoE. 
 
Figure 69: O&M cost. Energy yield and LCoE comparison of 2 monitoring scenarios: Monitoring vs. 
no monitoring. 
Summary 
Cost-effective monitoring solutions can: 
• Reflect financial KPIs (performance guarantees, allowed maintenance, integrate simula-
tions) 
• Allow “real-time” data processing for availability, alarms, warnings 
• Automate performance analysis and characterization in terms of kWh and $ 
(loss separation, sensitivity to irradiation, weather, cleaning, … ) 
• Implement preventive maintenance strategies 
Advanced monitoring algorithms lead to: 
• Providing investors with reliable information about O&M, track record & plant perfor-
mance, control 
• Separating and identifying losses where “actual vs. target” differs  
• Optimizing plant performance during lifetime 
• Reducing LCoE based on advanced monitoring design (characteristic trends, Loss Factor 
Model) 
• Reducing risk for investors & Independent Power Producers (IPPs) 

84 
 
More details and references can be found at www.gantner-webportal.com. 
3.6.6 System Performance and Degradation Analysis of Different PV Technologies 
The presentation by Yuzuru Ueda from the Tokyo University of Science focused on two topics: (1) 
a performance modeling approach (the sophisticated verification (SV) method) that quantifies 
energy losses in a PV system and (2) a review of performance monitoring and de gradation data 
collected as part of two long-term PV field deployment projects in Japan and the U.S. 
The SV method focuses on defining a series of loss factors that are applied in series to the availa-
ble insolation incident on  the area of the PV array in o rder to calculate the AC electricity that is 
generated by the system. Figure 70 shows the factors considered in the model and displays sever-
al of the equations used to determine the factors. 
The second part of the presentation focused on long -term monitoring results from two PV field 
sites in Japan ( Figure 71) and the U .S. (Figure 72). Performance ratios and effective peak power 
were used to compare performance levels over time at the Hokuto site (Figure 73).  Effective peak 
power is the power measured at 1  000 W/m 2 corrected for temperature, spectrum, reflection, 
and DC wiring losses.  Data influenced by shading, MPP mismatch and periods with high irradiance 
variability are filtered out. Effective peak power is used to estimate degradation rates.  Results 
show degradation rates of -0.57%/year for sc-Si and -0.50%/year for mc-Si modules at the Hokuto 
site.  The data set from the Los Alamos site, which begins in 2012, is not yet long enough to show 
clear degradation trends. 
 
 
Figure 70:  Diagram showing the loss factors considered by the SV method.  The equations for se v-
eral of the factors are shown. 

85 
 
 
 
Figure 71:  The Hokuto testing site in Japan hosts modules from 26 different manufacturers. 
 

86 
 
 
Figure 72:  The Los Alamos testing site in New Mexico, USA. 
 
 
Figure 73:  Summary of field-measured degradation of single crystalline (sc-Si) and multicrystalline 
Si (mc-Si) modules from the Hokuto site since 2008. 
  

87 
 
3.7 Poster Session 
Each poster presenter had an opportunity to provide a 1 -minute, 1-slide oral introduction to their 
poster in front of the entire workshop audience just prior to the general poster session.  This for-
mat worked well to provide the audience with a general idea of the poster topics and the i m-
portant results contained therein.  The full list of posters is documented  below in Table 10.  Post-
er presenters were also offered the opportunity to submit a written summary of their poster to be 
included in this report.  Only one of the presenters submitted a summary , which is included b e-
low.  Readers interested in learning more about any of the posters  are encouraged to contact the 
authors directly. 
  
88 
 
Table 10: List of poster presentations 
# Title Authors Affiliation Country 
P1 Investigating the Impact of Clouds on 
Solar Energy Production – Uncertainties 
for Yield Predictions by  Using Satellite 
Data for Clouds 
Ina Neher, 
Evandro Dresch, 
Khurshid Hasan, 
Bernd Evers -
Dietze, Dieter 
Franke and Stef a-
nie K. Meilinger 
Hochschule Bonn -
Rhein-Sieg 
Germany 
P2 Simulation of PV Power Output by I m-
plementation of a Spectral ly Dependent 
Photocurrent in the Double Diode Model 
Evandro Dresch Hochschule Bonn -
Rhein-Sieg 
Germany 
P3 Spectral Analysis of Various Thin Film 
Modules Using High Precision Spectral 
Response Data and Solar Spectral Irrad i-
ance Data 
Markus Schweiger, 
Ulrike J ahn, We r-
ner Herrmann  
TÜV Rheinland, 
Solar Energy 
Germany 
P4 Numerical Modeling of c -Si PV Modules 
by Coupling the Semiconductor with the 
Thermal Conduction, Convection and 
Radiation Equations 
Malte Vogt Institut für S o-
larener-
gieforschung 
GmbH 
Germany 
P5 Soiling and Self -Cleaning of PV Modules 
in Different Climates 
Werner Herrmann TÜV Rheinland, 
Solar Energy 
Germany 
P6  Bifacial Performance Field Data Analysis Mike Francis, T e-
resa Zhang, Bra n-
don Tracey 
SunEdison USA 
P7 A New Software for PV Plant Modeling Gianluca Corbellini SUPSI Switzerland 
P8 Progress and Challenges of CPV Modeling Tobias Gerstmaier, 
T. Zech, M. Röt t-
ger, C. Braun, A. 
Gombert 
Soitec Solar GmbH Germany 
P9 Uncertainty and Sensitivity Analysis for 
Photovoltaic System Models 
Clifford Hansen, 
Curtis Martin 
Sandia National 
Laboratories  
USA 
P10 Data Requirements for Calibration of 
Photovoltaic System Models 
Clifford Hansen, 
Kathrine Klise 
Sandia National 
Laboratories  
USA 
P11 Comparing Measured Performance Data 
of PV Installations to Simulation Results 
Bruno Wittmer PVsyst Switzerland 
P12 Field Monitoring and Validation of PV 
Performance Models (tbc) 
Frank Vignola, 
Fotis Mavrom a-
takis 
University of Or e-
gon 
USA 
P13 Big-data Analytics of Real -world I -V, Pmp 
Time Series to Validate Models and E x-
tract Mechanistic Insights to Lifetime 
Performance 
Roger French, Tim 
Peshek 
Case Western 
Reserve University 
USA 
P14 Effect of time -averaging on PV produ c-
tion estimates on systems with high DC to 
AC ratios 
William Hobbs Southern Company USA 
89 
 
3.7.1 Big-data Analytics of Real-world I-V, Pmp Time Series to Validate Models and Ex-
tract Mechanistic Insights to Lifetime Performance  
Authors: Roger H. French, Laura S. Bruckman, Timothy J. Peshek, Yang Hu, Nicholas R. Wheeler 
Solar Durability and Lifetime Extension Research Center, Case Western Reserve University, 
Cleveland, Ohio, USA. 
 
The study of real materials systems undergoing real-world operation and degradation processes is 
a challenging problem in the area of mesoscale science. Our res earch focus is on the temporal 
evolution of electrical properties and behavior of photovoltaic energy materials, particularly cry s-
talline silicon solar cells that contain a series of distinct and critically important interfaces , which 
play an essential rol e in the performance and degradation of PV modules over their lifetime. The 
central problem is that of incorporating real-world performance data, which is massive but info r-
mationally sparse (Pmp versus time  for example), with laboratory-based data from con firmatory 
experiments, which can be informationally  dense but suffers from low statistics. In the interfaces 
and chemical interactions among the screen -printed silver metallization grid on the front of the 
solar cells, which is applied as a paste consistin g of silver nanoparticles, glass frit, various organic 
binders and subsequently fired, and corrosion from acetic acid  produced in the ethylene  vinyl 
acetate encapsulant in front of the c-Si cell, there are myriad interfaces and potentially non-linear 
overall responses. These responses can be studied microscopically in the laboratory  but the rela-
tionship to real performance must be inferred. 
Modeling the underlying performance and performance degradation of screen -printed silver con-
tacts by a single diode and series and parallel resistances will likely miss the complexity of beha v-
ior because the diode model lacks the essential parameters for this complex materials system. 
The series resistance in particular comprises several contributors and is not unrelated to the shunt 
resistance or recombination current in real devices. However, by studying the massive real -world 
data streams themselves, new insights that are typically not modeled from physics -based models 
can provide new insights into complex behavior. 
The behavior of the solar cells is determined by the IV  curve shape, regardless of its relationship  
to the diode models. These shapes form the basis of what can be used for automated feature 
selection among huge data sets of IV curves. Further, there exist “change points”, which are 
points in the IV  curve where bypass diodes become forward-biased and turn on due to module 
heterogeneities. These heterogeneities can include cell cracking and hot spots for example and 
are more closely linked to the mesoscale degradation processes affecting localized areas. 
Building upon the diode modeling, some researchers have utilized Simulation Programs with Inte-
grated Circuit Emphasis (SPICE) to  simulate behavior of the  equivalent circuits. We  invoked this 
type of modeling to rapidly step through simulation scenarios and test hypotheses related to  het-
erogeneity to link real- world and laboratory datasets  (e.g., Figure 74). Our models started with a 
single-diode model for each cell, with the ability to vary series and shunt resistors, diode param e-
ters as well as illumination. This  simple model was used to test the behavior of bypass diodes 
under forward and reverse bias conditio ns and simulate a large matrix of conditions related to 
changing the series and shunt resistors,  photo-generated current, and any diode parameter we 
choose. 
We simulated the performance of a 4 -cell mini-module with high heterogeneity and then tested 
that simulation experimentally. The data support the interpretation that an increase in the series 
resistance, which itself comprise s many factors, is linked to the shunt resistance in that the r e-
sistance cannot support fully the available current and more phot o-generated carriers are recom-
90 
 
bining even if the  characteristic scattering time is unchanged in the bulk. The mini -module fabri-
cated with the damaged cell  showed bypass diode turn -on under uniform irradiance, due to the 
resistances of the cells being stron gly non-uniform. This observation demonstrates the potential 
for real-world modules to show bypassing even  under uniform illumination if a localized cell or 
interconnect becomes highly resistive. A scenario in which this observable may be found is loca l-
ized hot spots, where positive thermal feedback occurs because the photo-generated carriers of a 
solar cell are thought of as a current source. At the SDLE SunFarm, over 1.5 million IV curves over 
500 days have been acquired at an average interval of 10 minutes. Using automated analytics, we 
can statistically model the behavior of PV modules and strings in detail. The signatures of interest 
in the data were guided initially  by the SPICE development, but  machine learning techniques can 
explore the data in a supervised manner, and then group the data by recognizable features in the 
IV data sets. 
A pairwise scatter and correlation matrix is a useful method for visualizing the lessons from these 
large amounts of data (e.g.,). As an example, Figure 75 shows several variables including the cu r-
rents at the intercept of each change point. Variables and their histograms are shown along the 
matrix diagonal. Below the diagonal are the pairwise scatter plots of the variables, and the corre-
sponding pairwise  linear correlation coefficient is shown above the diagonal. This visualization 
method allows for quick processing of big data. 
Big data analytics is becoming a commonplace term today, and one that is being invoked in mate-
rials science. We have demonstrated the feasibility and novelty of studying large  IV data sets us-
ing machine learning techniques, and those guided by mesoscopic insights into system -
heterogeneous behavior. The IV curves form a linkage to the laboratory where hypothetical de g-
radation scenarios can be verified and a more conventional materials characterization process can 
be undertaken to identify and understand the behavior and dynamics of mechanisms. These lin k-
ages then allow for a n unbiased approach to mesoscale science applied rigorously to the vast 
scale of real-world photovoltaic deployment. 
Figure 74:  Examples of modeled (left) versus measured (right) IV curves. 

91 
 
 
Figure 75:  Example of a pairwise scatter and correlation matrix. 
 

92 
 
References 
[1] "2015 4th PV Performance Modeling and Monitoring Workshop", PV Performance Modeling 
Collaborative, 2017. [Online]. Available: https://pvpmc.sandia.gov/resou rces-and-
events/events/2015-4th-pv-performance-modeling-and-monitoring-workshop/. [Accessed: 27 - 
Feb- 2017]. 
[2] Cameron, C., J. Stein and C. Tasca (2011). PV Performance Modeling Workshop Summary R e-
port. Albuquerque, NM, Sandia National Laboratories. SAND2011-3419 
[3] Box, G. E. P. and N. R. Draper (1986). Empirical model- building and response surface . New 
York, NY, John Wiley & Sons, Inc. 
[4] Maxwell, E. L. (1987). A Quasi-Physical Model for Converting Hourly Global Horizontal to Direct 
Normal Insolation. Golden, CO, Solar Energy Research Institute. 
[5] Perez, R., P. Ineichen, E. L. Maxwell, R. Seals and A. Zelenka (1992). "Dynamic Global- to-Direct 
Irradiance Conversion Models." ASHRAE Transactions 98(1). 
[6] "Albedo", PV Performance Modeling Collaborative , 2017. [Online]. Available: 
https://pvpmc.sandia.gov/modeling-steps/1-weather-design-inputs/plane-of-array-poa-
irradiance/calculating-poa-irradiance/poa-ground-reflected/albedo/. [Accessed: 27 - Feb- 2017]. 
[7] Hay, J. E. and J. A. Davies (1980). Calculati ons of the solar radiation incident on an inclined 
surface. First Canadian Solar Radiation Data Workshop . J. E. Hay and T. K. Won. Canada, Ministry 
of Supply and Services. 
[8] Paltridge, G. W. and C. M. R. Platt (1976). Radiative processes in meteorology and climatology .  
New York, Elsevier Scientific Pub. Co. 
[9] Reindl, D. T., W. A. Beckman and J. A. Duffie (1990). "Evaluation of Hourly Tilted Surface Radia-
tion Models." Solar Energy 45(1): 9-17. 
[10] Perez, R., P. Ineichen and R. Seals (1990). "Modeling Daylight Availability and Irradiance Com-
ponents from Direct and Global Irradiance." Solar Energy 44(5): 271-289. 
[11] Martin, N. and J. M. Ruiz (2001). "Calculation of the PV modules angular losses under field 
conditions by means of an analytical model." Solar Energy 70: 25-38. 
[12] "File:Solar spectrum ita.svg - Wikimedia Commons", Commons.wikimedia.org, 2017. [Online]. 
Available: http://commons.wikimedia.org/wiki/File:Solar_spectrum_ita.svg. [Accessed: 27 - Feb- 
2017]. 
[13] "Spectral Response", PV Perfrom ance Modeling Collaborative , 2017. [Online]. Available: 
https://pvpmc.sandia.gov/modeling-steps/2-dc-module-iv/effective-irradiance/spectral-
response/. [Accessed: 27- Feb- 2017]. 
[14] King, D. L., E. E. Boyson and J. A. Kratochvil (2004). Photovoltaic Array Performance Model. 
Albuquerque, NM, Sandia National Laboratories. SAND2004-3535. 
[15] Faiman, D. (2008). "Assessing the outdoor operating temperature of photovoltaic modules." 
Progress in Photovoltaics 16(4): 307-315. 
[16] Ross, R.G. and M.I. Smokler (1986). Flat-Plate Array Project – Final Report Vol. VI: Engineering 
Sciences and Reliability, JPL Pub. No. 86-31. 
93 
 
[17] Skoplaki, E. and J. A. Palyvos (2009). "Operating temperature of photovoltaic modules: A su r-
vey of pertinent correlations." Renewable Energy 34(1): 23-29. 
[18] Luketa-Hanlin, A. and J. S. Stein (2012). Improvement and Validation of a Transient Model To 
Predict Photovoltaic Module Temperature. World Renewable Energy Forum. Denver, CO. 
[19] De Soto, W., S. A. Klei n and W. A. Beckman (2006). "Improvement and validation of a model 
for photovoltaic array performance." Solar Energy 80(1): 78-88. 
[20] "Home", Pvsyst.com, 2017. [Online]. Available: http://www.pvsyst.com/en/. [Accessed: 27 - 
Feb- 2017]. 
[21] Sellner, S., J. Sutterlueti, L. Schreier and S. Ransome (2012). "Advanced PV module perfo r-
mance characterization and validation using the novel Loss Factors Model." 38th IEEE PVSC: 2938-
2943. 
[22] Stein, J. S., J. Sutterlueti, S. Ransome, C. W. Hansen and B. H. King (2 013). Outdoor PV Pe r-
formance Evaluation of Three Different Models: Single -diode, SAPM and Loss Factor Model. 28th 
EU PVSEC. Paris, France. 
[23] "PVWatts Calculator", Pvwatts.nrel.gov, 2017. [Online]. Available: http://pvwatts.nrel.gov/. 
[Accessed: 27- Feb- 2017]. 
[24] King, D. l., S. Gonzalez, G. M. Galbraith and W. E. Boyson (2007). Performance Model for Grid-
Connected Photovoltaic Inverters . Albuquerque, NM, Sandia National Laboratories. SAND2007-
5036. 
[25] Driesse, A., P. Jain and S. Harrison (2008). Bey ond the Curves: Modeling the Electrical Effi-
ciency of Photovoltaic Inverters. 33rd IEEE PVSC San Diego, CA: 1935-1940. 
[26] "CAMS radiation service -  www.soda-pro.com", Soda -pro.com, 2017. [Online]. Available: 
http://www.soda-pro.com/web-services/radiation/cams-radiation-service. [Accessed: 27 - Feb- 
2017]. 
[27] "ENDORSE FP7 project | ENDORSE (ENergy DOwnstReam SErvices)", Endorse -fp7.eu, 2017. 
[Online]. Available: http://www.endorse-fp7.eu/. [Accessed: 27- Feb- 2017]. 
[28] "Copernicus Atmosphere Monitoring Service |", Atmosphere.copernicus.eu, 2017. [Online]. 
Available: http://atmosphere.copernicus.eu/. [Accessed: 27- Feb- 2017]. 
[29] "MACC Project - Home", Gmes-atmosphere.eu, 2017. [Online]. Available: http://ww w.gmes-
atmosphere.eu/. [Accessed: 27- Feb- 2017]. 
[30] "Home - OrPHEuS project", Orpheus -project.eu, 2017. [Online]. Available: 
http://www.orpheus-project.eu. [Accessed: 27- Feb- 2017]. 
[31] "Meteonorm: Irradiation data forevery place on Earth", Meteonorm. com, 2017. [Online]. 
Available: http://www.meteonorm.com. [Accessed: 27- Feb- 2017]. 
[32] "Homepage - GEBA", Geba.ethz.ch, 2017. [Online]. Available: http://www.geba.ethz.ch/. 
[Accessed: 27- Feb- 2017]. 
[33] Ineichen, P. (2008). "A broadband simplified version of the Solis clear sky model." Solar Ener-
gy 82(8): 758-762. 
[34] Marion, W., A. Anderberg, C. Deline, S. Glick, M. Muller, G. Perrin, J. Rodriguez, S. R. , K. Te r-
williger and T. J. Silverman (2014). User’s Manual for Data for Validating Models for PV Module 
Performance. Golden, CO, National Renewable Energy Laboratory. NREL/TP-5200-61610. 
94 
 
[35] Nelson, L., M. Frichtl and A. Panchula (2012). "Changes in cadmium telluride photovoltaic 
system performance due to spectrum." Journal of Photovoltaics 3(1): 488-493. 
[36] Haurwitz, B. (1946). "Insolation in Relation to Cloud Type." Journal of Meteorology  3: 123-
124. 
[37] D. Ryberg and J. Freeman, "Integration, Validation, and Application of a PV Snow Coverage 
Model in SAM", National Renewable Energy Laboratory, 2015. 
[38] Marion, B., R. Schaefer, H. Caine and G. Sanchez (2013). "Measured and modeled photovolta-
ic system energy losses from snow for Colorado and Wisconsin locations." Solar Energy  97: 112-
121. 
[39] Winter, M. et al., "Impact of realistic illumination on optical losses in Si solar cell modules 
compared to standard testing conditions”, EUPVSEC, 2015 
[40] Ernst, M., H. Holst, M. Winter and P. P. Altermatt (2016). "SunCalculator: A program to calc u-
late the angular and spectral distribution of direct and diffuse solar radiation." Solar Energy Mate-
rials and Solar Cells 157: 913-922. 
[41] Holst, H., M. Winter, M. R. Vogt, K. Bothe, M. Köntges, R. Brendel and P. P. Altermatt (2013). 
"Application of a New Ray Tracing Framework to the Analysis of Extended Regions in Si Solar Cell 
Modules." Energy Procedia 38: 86-93. 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
95 
 
 
 
 
 
For further information about the IEA Photovoltaic Power Systems Program and Task 13 public a-
tions, please visit www.iea-pvps.org
.  
  
96
