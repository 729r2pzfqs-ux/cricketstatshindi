#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ICC tournament aggregation for cricketstatshindi.com.

Scans the raw Cricsheet match files (data/raw/*_json/) and builds, for each
edition of the ICC Cricket World Cup (ODI), the ICC T20 World Cup and the ICC
Champions Trophy, a structured dict the generator turns into HTML:

  * match results grouped by stage / group
  * knockout results (quarter / semi / final)
  * the raw final match (for an inline scorecard)
  * top run-scorers and top wicket-takers across the edition
  * curated Hindi host + storyline + player-of-the-tournament

The Cricsheet snapshot is not always complete for every edition, so we present
*match results* rather than computed points tables, and label aggregate top
performers as "based on available matches". Imported by generate.py.
"""
import json
import glob
from pathlib import Path
from collections import defaultdict

# ----------------------------------------------------------------------------
# Edition configuration. winner / runner-up / margin are derived from the data;
# host, storyline and player-of-the-tournament (pot) are curated for accuracy.
# pot is a Cricsheet-style short name so it can link to the player page.
# ----------------------------------------------------------------------------
TOURNAMENTS = [
    {
        "key": "world-cup",
        "title": "आईसीसी क्रिकेट विश्व कप",
        "short": "विश्व कप",
        "fmt": "ODI",
        "folder": "odis_json",
        "names": {"ICC Cricket World Cup", "ICC World Cup", "World Cup"},
        "quota": 50,
        "intro":
            "आईसीसी क्रिकेट विश्व कप पुरुष एकदिवसीय क्रिकेट का सबसे बड़ा मंच है, जिसे "
            "हर चार साल में आयोजित किया जाता है। 1975 में शुरू हुआ यह टूर्नामेंट दुनिया "
            "भर के करोड़ों प्रशंसकों के लिए क्रिकेट का सबसे प्रतिष्ठित ख़िताब है। नीचे "
            "उन सभी संस्करणों का विस्तृत ब्योरा है जिनका बॉल-बाय-बॉल डेटा उपलब्ध है — "
            "मेज़बान, चैंपियन, नॉकआउट नतीजे, फ़ाइनल स्कोरकार्ड और शीर्ष प्रदर्शनकर्ता।",
        "desc":
            "आईसीसी क्रिकेट विश्व कप (वनडे) के सभी संस्करण हिंदी में — चैंपियन, फ़ाइनल "
            "स्कोरकार्ड, सर्वाधिक रन, सर्वाधिक विकेट और प्लेयर ऑफ़ द टूर्नामेंट।",
        "editions": [
            {"season": "2002/03", "year": "2003",
             "host": "दक्षिण अफ़्रीका, ज़िम्बाब्वे व केन्या", "pot": "SR Tendulkar",
             "story":
                "2003 का विश्व कप दक्षिण अफ़्रीका में खेला गया, जहाँ रिकी पोंटिंग की "
                "ऑस्ट्रेलियाई टीम पूरे टूर्नामेंट में एक भी मैच नहीं हारी। फ़ाइनल में "
                "जोहान्सबर्ग के वांडरर्स मैदान पर ऑस्ट्रेलिया ने भारत को बड़े अंतर से "
                "हराकर लगातार दूसरा ख़िताब जीता। सचिन तेंदुलकर ने रिकॉर्ड 673 रन बनाकर "
                "प्लेयर ऑफ़ द टूर्नामेंट का पुरस्कार जीता।"},
            {"season": "2006/07", "year": "2007",
             "host": "वेस्टइंडीज़", "pot": "GD McGrath",
             "story":
                "2007 का विश्व कप पहली बार कैरिबियाई द्वीपों में आयोजित हुआ। ऑस्ट्रेलिया "
                "ने अपना दबदबा क़ायम रखते हुए लगातार तीसरा ख़िताब जीता और बारबाडोस में "
                "बारिश से प्रभावित फ़ाइनल में श्रीलंका को डकवर्थ-लुईस नियम से हराया। "
                "ग्लेन मैकग्रा अपने आख़िरी टूर्नामेंट में सर्वाधिक विकेट लेकर प्लेयर ऑफ़ "
                "द टूर्नामेंट रहे।"},
            {"season": "2010/11", "year": "2011",
             "host": "भारत, श्रीलंका व बांग्लादेश", "pot": "Yuvraj Singh",
             "story":
                "2011 का विश्व कप भारतीय उपमहाद्वीप में खेला गया और मेज़बान भारत ने "
                "महेंद्र सिंह धोनी की कप्तानी में 28 साल बाद ख़िताब जीता। मुंबई के "
                "वानखेड़े मैदान पर फ़ाइनल में धोनी के विजयी छक्के ने श्रीलंका को हराया "
                "और सचिन तेंदुलकर के विश्व कप जीतने का सपना पूरा किया। युवराज सिंह "
                "ऑलराउंड प्रदर्शन के दम पर प्लेयर ऑफ़ द टूर्नामेंट बने।"},
            {"season": "2014/15", "year": "2015",
             "host": "ऑस्ट्रेलिया व न्यूज़ीलैंड", "pot": "MA Starc",
             "story":
                "2015 का विश्व कप ऑस्ट्रेलिया और न्यूज़ीलैंड में संयुक्त रूप से खेला "
                "गया। मेलबर्न के विशाल एमसीजी में हुए फ़ाइनल में ऑस्ट्रेलिया ने "
                "न्यूज़ीलैंड को हराकर रिकॉर्ड पाँचवाँ ख़िताब जीता। तेज़ गेंदबाज़ मिचेल "
                "स्टार्क ने अपनी घातक स्विंग से प्लेयर ऑफ़ द टूर्नामेंट का पुरस्कार "
                "जीता।"},
            {"season": "2019", "year": "2019",
             "host": "इंग्लैंड व वेल्स", "pot": "KS Williamson",
             "story":
                "2019 का विश्व कप क्रिकेट इतिहास के सबसे नाटकीय फ़ाइनल के लिए याद किया "
                "जाता है। लॉर्ड्स में इंग्लैंड और न्यूज़ीलैंड का मुक़ाबला पहले टाई रहा, "
                "फिर सुपर ओवर भी टाई हुआ और इंग्लैंड को अधिक बाउंड्री लगाने के आधार पर "
                "विजेता घोषित किया गया — इस तरह इंग्लैंड ने अपना पहला विश्व कप जीता। "
                "न्यूज़ीलैंड के कप्तान केन विलियमसन प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2023/24", "year": "2023",
             "host": "भारत", "pot": "V Kohli",
             "story":
                "2023 का विश्व कप भारत में खेला गया, जहाँ मेज़बान टीम लगातार दस मैच "
                "जीतकर अपराजेय रूप में फ़ाइनल तक पहुँची। लेकिन अहमदाबाद के नरेंद्र मोदी "
                "स्टेडियम में फ़ाइनल में ऑस्ट्रेलिया ने भारत को हराकर छठा ख़िताब जीता। "
                "विराट कोहली ने एक ही विश्व कप में रिकॉर्ड 765 रन बनाकर प्लेयर ऑफ़ द "
                "टूर्नामेंट का पुरस्कार जीता।"},
        ],
    },
    {
        "key": "t20-world-cup",
        "title": "आईसीसी टी20 विश्व कप",
        "short": "टी20 विश्व कप",
        "fmt": "T20I",
        "folder": "t20s_json",
        "names": {"ICC World Twenty20", "World T20", "ICC Men's T20 World Cup"},
        "quota": 20,
        "intro":
            "आईसीसी टी20 विश्व कप पुरुष ट्वेंटी-20 क्रिकेट का विश्व चैंपियनशिप टूर्नामेंट "
            "है, जिसकी शुरुआत 2007 में हुई। तेज़-तर्रार और रोमांच से भरपूर इस प्रारूप ने "
            "क्रिकेट को नई पीढ़ी तक पहुँचाया और कई यादगार फ़ाइनल दिए। नीचे उन सभी "
            "संस्करणों का विवरण है जिनका डेटा उपलब्ध है।",
        "desc":
            "आईसीसी टी20 विश्व कप के सभी संस्करण हिंदी में — चैंपियन, फ़ाइनल स्कोरकार्ड, "
            "सर्वाधिक रन, सर्वाधिक विकेट और प्लेयर ऑफ़ द टूर्नामेंट।",
        "editions": [
            {"season": "2007/08", "year": "2007",
             "host": "दक्षिण अफ़्रीका", "pot": "Shahid Afridi",
             "story":
                "टी20 विश्व कप का पहला संस्करण 2007 में दक्षिण अफ़्रीका में खेला गया। "
                "जोहान्सबर्ग में हुए रोमांचक फ़ाइनल में महेंद्र सिंह धोनी की युवा भारतीय "
                "टीम ने पाकिस्तान को आख़िरी ओवर में हराकर पहला ख़िताब जीता और इस नए "
                "प्रारूप को भारत में घर-घर लोकप्रिय बना दिया।"},
            {"season": "2009", "year": "2009",
             "host": "इंग्लैंड", "pot": "TM Dilshan",
             "story":
                "2009 का टी20 विश्व कप इंग्लैंड में खेला गया, जहाँ यूनुस ख़ान की "
                "कप्तानी में पाकिस्तान ने फ़ाइनल में श्रीलंका को हराकर ख़िताब जीता। "
                "श्रीलंका के तिलकरत्ने दिलशान अपने 'दिलस्कूप' शॉट और शानदार बल्लेबाज़ी "
                "के दम पर प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2010", "year": "2010",
             "host": "वेस्टइंडीज़", "pot": "KP Pietersen",
             "story":
                "2010 का टी20 विश्व कप वेस्टइंडीज़ में आयोजित हुआ। बारबाडोस के फ़ाइनल "
                "में इंग्लैंड ने ऑस्ट्रेलिया को हराकर अपना पहला आईसीसी वैश्विक ख़िताब "
                "जीता। केविन पीटरसन को प्लेयर ऑफ़ द टूर्नामेंट चुना गया।"},
            {"season": "2012/13", "year": "2012",
             "host": "श्रीलंका", "pot": "SR Watson",
             "story":
                "2012 का टी20 विश्व कप श्रीलंका में खेला गया। कोलंबो के फ़ाइनल में "
                "वेस्टइंडीज़ ने मेज़बान श्रीलंका को हराकर अपना पहला टी20 ख़िताब जीता "
                "और जश्न में 'गंगनम स्टाइल' डांस सुर्ख़ियों में रहा। शेन वॉटसन प्लेयर "
                "ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2013/14", "year": "2014",
             "host": "बांग्लादेश", "pot": "V Kohli",
             "story":
                "2014 का टी20 विश्व कप बांग्लादेश में आयोजित हुआ। ढाका के फ़ाइनल में "
                "श्रीलंका ने भारत को हराकर ख़िताब जीता — यह कुमार संगकारा और महेला "
                "जयवर्धने का आख़िरी टी20 अंतरराष्ट्रीय टूर्नामेंट था। विराट कोहली ने "
                "शानदार बल्लेबाज़ी से प्लेयर ऑफ़ द टूर्नामेंट का पुरस्कार जीता।"},
            {"season": "2015/16", "year": "2016",
             "host": "भारत", "pot": "V Kohli",
             "story":
                "2016 का टी20 विश्व कप भारत में खेला गया। कोलकाता के ईडन गार्डन्स में "
                "हुए फ़ाइनल में वेस्टइंडीज़ ने इंग्लैंड को हराया, जहाँ कार्लोस "
                "ब्रैथवेट ने आख़िरी ओवर में लगातार चार छक्के जड़कर इतिहास रच दिया। "
                "विराट कोहली लगातार दूसरी बार प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2021/22", "year": "2021",
             "host": "संयुक्त अरब अमीरात व ओमान", "pot": "DA Warner",
             "story":
                "2021 का टी20 विश्व कप कोविड-19 के कारण संयुक्त अरब अमीरात और ओमान में "
                "खेला गया, हालाँकि इसकी मेज़बानी भारत के पास थी। दुबई के फ़ाइनल में "
                "ऑस्ट्रेलिया ने न्यूज़ीलैंड को हराकर अपना पहला टी20 विश्व कप जीता। "
                "डेविड वॉर्नर प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2022/23", "year": "2022",
             "host": "ऑस्ट्रेलिया", "pot": "SM Curran",
             "story":
                "2022 का टी20 विश्व कप ऑस्ट्रेलिया में आयोजित हुआ। मेलबर्न के एमसीजी "
                "में हुए फ़ाइनल में इंग्लैंड ने पाकिस्तान को हराकर दूसरी बार ख़िताब "
                "जीता और एक साथ वनडे व टी20 दोनों का विश्व चैंपियन बनने वाली पहली टीम "
                "बनी। बाएँ हाथ के गेंदबाज़ सैम करन प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2024", "year": "2024",
             "host": "वेस्टइंडीज़ व अमेरिका", "pot": "JJ Bumrah",
             "story":
                "2024 का टी20 विश्व कप पहली बार वेस्टइंडीज़ और संयुक्त राज्य अमेरिका "
                "में संयुक्त रूप से खेला गया। बारबाडोस के फ़ाइनल में रोहित शर्मा की "
                "भारतीय टीम ने दक्षिण अफ़्रीका को हराकर ख़िताब जीता और पूरे टूर्नामेंट "
                "में अपराजेय रही। जसप्रीत बुमराह अपनी घातक गेंदबाज़ी से प्लेयर ऑफ़ द "
                "टूर्नामेंट बने।"},
            {"season": "2025/26", "year": "2026",
             "host": "भारत व श्रीलंका", "pot": None,
             "story":
                "2026 का टी20 विश्व कप भारत और श्रीलंका में आयोजित हुआ। नीचे उपलब्ध "
                "मैच डेटा के आधार पर इस संस्करण के नॉकआउट नतीजे, फ़ाइनल स्कोरकार्ड और "
                "शीर्ष प्रदर्शनकर्ता दिए गए हैं।"},
        ],
    },
    {
        "key": "champions-trophy",
        "title": "आईसीसी चैंपियंस ट्रॉफ़ी",
        "short": "चैंपियंस ट्रॉफ़ी",
        "fmt": "ODI",
        "folder": "odis_json",
        "names": {"ICC Champions Trophy"},
        "quota": 50,
        "intro":
            "आईसीसी चैंपियंस ट्रॉफ़ी एकदिवसीय क्रिकेट का दूसरा सबसे बड़ा वैश्विक "
            "टूर्नामेंट है, जिसे अक्सर 'मिनी विश्व कप' कहा जाता है। इसमें केवल शीर्ष "
            "रैंकिंग वाली टीमें हिस्सा लेती हैं, जिससे हर मैच कड़ा और रोमांचक होता है। "
            "नीचे उन सभी संस्करणों का ब्योरा है जिनका डेटा उपलब्ध है।",
        "desc":
            "आईसीसी चैंपियंस ट्रॉफ़ी के सभी संस्करण हिंदी में — चैंपियन, फ़ाइनल "
            "स्कोरकार्ड, सर्वाधिक रन, सर्वाधिक विकेट और शीर्ष प्रदर्शनकर्ता।",
        "editions": [
            {"season": "2004", "year": "2004",
             "host": "इंग्लैंड", "pot": None,
             "story":
                "2004 की चैंपियंस ट्रॉफ़ी इंग्लैंड में खेली गई। लंदन के ओवल मैदान पर "
                "हुए कड़े फ़ाइनल में वेस्टइंडीज़ ने आख़िरी विकेट की साझेदारी के सहारे "
                "मेज़बान इंग्लैंड को हराकर ख़िताब जीता।"},
            {"season": "2006/07", "year": "2006",
             "host": "भारत", "pot": None,
             "story":
                "2006 की चैंपियंस ट्रॉफ़ी भारत में आयोजित हुई। मुंबई के फ़ाइनल में "
                "ऑस्ट्रेलिया ने वेस्टइंडीज़ को हराकर पहली बार यह ख़िताब जीता।"},
            {"season": "2009/10", "year": "2009",
             "host": "दक्षिण अफ़्रीका", "pot": None,
             "story":
                "2009 की चैंपियंस ट्रॉफ़ी दक्षिण अफ़्रीका में खेली गई। फ़ाइनल में "
                "ऑस्ट्रेलिया ने न्यूज़ीलैंड को हराकर लगातार दूसरी बार ख़िताब अपने नाम "
                "किया।"},
            {"season": "2013", "year": "2013",
             "host": "इंग्लैंड व वेल्स", "pot": "S Dhawan",
             "story":
                "2013 की चैंपियंस ट्रॉफ़ी इंग्लैंड में खेली गई और महेंद्र सिंह धोनी की "
                "कप्तानी में भारत ने ख़िताब जीता। बर्मिंघम के बारिश से छोटे हुए फ़ाइनल "
                "में भारत ने मेज़बान इंग्लैंड को हराया। शिखर धवन सर्वाधिक रन बनाकर "
                "प्लेयर ऑफ़ द टूर्नामेंट रहे।"},
            {"season": "2017", "year": "2017",
             "host": "इंग्लैंड व वेल्स", "pot": None,
             "story":
                "2017 की चैंपियंस ट्रॉफ़ी इंग्लैंड में खेली गई। ओवल में हुए फ़ाइनल में "
                "पाकिस्तान ने फ़खर ज़मान के शतक और शानदार गेंदबाज़ी के दम पर भारत को "
                "बड़े अंतर से हराकर पहली बार यह ख़िताब जीता।"},
            {"season": "2024/25", "year": "2025",
             "host": "पाकिस्तान व संयुक्त अरब अमीरात", "pot": None,
             "story":
                "2025 की चैंपियंस ट्रॉफ़ी की मेज़बानी पाकिस्तान के पास थी और भारत के "
                "मैच दुबई में खेले गए। दुबई के फ़ाइनल में भारत ने न्यूज़ीलैंड को हराकर "
                "रिकॉर्ड तीसरी बार यह ख़िताब जीता।"},
        ],
    },
]

# stage -> Hindi label + sort order. Anything not listed is a group/league match.
KNOCKOUT = {
    "Final": ("फ़ाइनल", 90),
    "Semi Final": ("सेमीफ़ाइनल", 80),
    "3rd Place": ("तीसरे स्थान का मुक़ाबला", 70),
    "Quarter Final": ("क्वार्टर फ़ाइनल", 60),
}

WICKET_TO_BOWLER = {"bowled", "caught", "lbw", "stumped",
                    "caught and bowled", "hit wicket"}


def _ev(info, key):
    e = info.get("event")
    return e.get(key) if isinstance(e, dict) else None


def _evname(info):
    e = info.get("event")
    return e.get("name", "") if isinstance(e, dict) else str(e)


def _margin_hi(info):
    """Human Hindi result string from the outcome block."""
    oc = info.get("outcome", {})
    method = oc.get("method")
    suffix = " (डी/एल)" if method == "D/L" else ""
    if oc.get("result") == "tie":
        elim = oc.get("eliminator")
        if elim:
            return f"{elim} सुपर ओवर में विजयी"
        return "मैच टाई"
    if oc.get("result") == "no result":
        return "कोई परिणाम नहीं"
    winner = oc.get("winner")
    if not winner:
        return oc.get("result", "—") or "—"
    by = oc.get("by", {})
    if "runs" in by:
        return f"{winner} {by['runs']} रन से विजयी{suffix}"
    if "wickets" in by:
        return f"{winner} {by['wickets']} विकेट से विजयी{suffix}"
    return f"{winner} विजयी{suffix}"


def parse_match(d, quota):
    """Parse one match into innings totals + per-player batting/bowling tallies."""
    info = d["info"]
    reg = info.get("registry", {}).get("people", {})
    innings_out = []
    bat_acc = {}   # id -> dict
    bowl_acc = {}  # id -> dict

    for inn in d.get("innings", []):
        team = inn.get("team", "")
        total = 0
        wkts = 0
        legal = 0
        # per-innings tallies for HS / best bowling tracking
        i_bat = {}
        i_bowl = {}
        for ov in inn.get("overs", []):
            for de in ov.get("deliveries", []):
                ex = de.get("extras", {})
                wide = "wides" in ex
                nb = "noballs" in ex
                bye = ex.get("byes", 0) + ex.get("legbyes", 0)
                rb = de["runs"]
                total += rb.get("total", 0)
                bt = de.get("batter")
                runs_b = rb.get("batter", 0)
                rec = i_bat.setdefault(bt, [0, 0, 0, 0, False])  # r,b,4,6,out
                rec[0] += runs_b
                if not wide:
                    rec[1] += 1
                if runs_b == 4:
                    rec[2] += 1
                elif runs_b == 6:
                    rec[3] += 1
                bw = de.get("bowler")
                brec = i_bowl.setdefault(bw, [0, 0, 0])  # balls, runs, wkts
                if not (wide or nb):
                    brec[0] += 1
                    legal += 1
                brec[1] += rb.get("total", 0) - bye - ex.get("penalty", 0)
                for w in de.get("wickets", []):
                    wkts += 1
                    po = w.get("player_out")
                    if po in i_bat:
                        i_bat[po][4] = True
                    if w.get("kind") in WICKET_TO_BOWLER:
                        brec[2] += 1
        ov_str = f"{legal // 6}.{legal % 6}"
        innings_out.append({"team": team, "runs": total, "wkts": wkts,
                            "overs": ov_str, "balls": legal})
        # fold innings tallies into match accumulators
        for name, r in i_bat.items():
            pid = reg.get(name, name)
            a = bat_acc.setdefault(pid, {"name": name, "runs": 0, "balls": 0,
                                         "fours": 0, "sixes": 0, "outs": 0,
                                         "inns": 0, "hs": 0, "hs_no": False})
            a["runs"] += r[0]; a["balls"] += r[1]; a["fours"] += r[2]
            a["sixes"] += r[3]; a["inns"] += 1
            if r[4]:
                a["outs"] += 1
            if r[0] > a["hs"] or (r[0] == a["hs"] and not r[4]):
                a["hs"] = r[0]; a["hs_no"] = not r[4]
        for name, r in i_bowl.items():
            pid = reg.get(name, name)
            a = bowl_acc.setdefault(pid, {"name": name, "balls": 0, "runs": 0,
                                          "wkts": 0, "inns": 0,
                                          "best_w": -1, "best_r": 0})
            a["balls"] += r[0]; a["runs"] += r[1]; a["wkts"] += r[2]; a["inns"] += 1
            if r[2] > a["best_w"] or (r[2] == a["best_w"] and r[1] < a["best_r"]):
                a["best_w"] = r[2]; a["best_r"] = r[1]

    return innings_out, bat_acc, bowl_acc


def collect(raw_dir):
    """Return TOURNAMENTS with each edition populated with computed data."""
    raw_dir = Path(raw_dir)
    out = []
    for t in TOURNAMENTS:
        # index raw files for this format once per tournament
        files_by_season = defaultdict(list)
        for fn in glob.glob(str(raw_dir / t["folder"] / "*.json")):
            try:
                d = json.load(open(fn))
            except Exception:
                continue
            info = d["info"]
            if info.get("gender") != "male":
                continue
            if _evname(info) not in t["names"]:
                continue
            files_by_season[str(info.get("season"))].append((fn, d))

        editions = []
        for ed in t["editions"]:
            entries = files_by_season.get(ed["season"], [])
            matches = []
            bat_tot = {}
            bowl_tot = {}
            final_raw = None
            for fn, d in entries:
                info = d["info"]
                innings, bat, bowl = parse_match(d, t["quota"])
                stage = _ev(info, "stage")
                grp = _ev(info, "group")
                m = {
                    "mid": Path(fn).stem,
                    "date": (info.get("dates") or [""])[0],
                    "stage": stage,
                    "group": grp,
                    "teams": info.get("teams", []),
                    "venue": info.get("venue", ""),
                    "city": info.get("city", ""),
                    "innings": innings,
                    "outcome": info.get("outcome", {}),
                    "winner": info.get("outcome", {}).get("winner"),
                    "margin": _margin_hi(info),
                    "pom": info.get("player_of_match", []) or [],
                }
                matches.append(m)
                if stage == "Final" and final_raw is None:
                    final_raw = d
                    m["is_final"] = True
                # accumulate batting
                for pid, a in bat.items():
                    g = bat_tot.get(pid)
                    if not g:
                        bat_tot[pid] = dict(a, pid=pid)
                    else:
                        g["runs"] += a["runs"]; g["balls"] += a["balls"]
                        g["fours"] += a["fours"]; g["sixes"] += a["sixes"]
                        g["outs"] += a["outs"]; g["inns"] += a["inns"]
                        if a["hs"] > g["hs"] or (a["hs"] == g["hs"] and a["hs_no"]):
                            g["hs"] = a["hs"]; g["hs_no"] = a["hs_no"]
                for pid, a in bowl.items():
                    g = bowl_tot.get(pid)
                    if not g:
                        bowl_tot[pid] = dict(a, pid=pid)
                    else:
                        g["balls"] += a["balls"]; g["runs"] += a["runs"]
                        g["wkts"] += a["wkts"]; g["inns"] += a["inns"]
                        if a["best_w"] > g["best_w"] or \
                           (a["best_w"] == g["best_w"] and a["best_r"] < g["best_r"]):
                            g["best_w"] = a["best_w"]; g["best_r"] = a["best_r"]

            matches.sort(key=lambda x: x["date"])
            knockouts = [m for m in matches if m["stage"] in KNOCKOUT]
            knockouts.sort(key=lambda m: (KNOCKOUT[m["stage"]][1], m["date"]))
            groups = [m for m in matches if m["stage"] not in KNOCKOUT]

            # final / runner-up / champion
            final_m = next((m for m in matches if m["stage"] == "Final"), None)
            champion = runner = None
            if final_m and final_m["winner"]:
                champion = final_m["winner"]
                runner = next((x for x in final_m["teams"]
                               if x != champion), None)
            elif final_m and final_m["outcome"].get("eliminator"):
                champion = final_m["outcome"]["eliminator"]
                runner = next((x for x in final_m["teams"]
                               if x != champion), None)

            # top performers
            def bat_avg(g):
                return round(g["runs"] / g["outs"], 1) if g["outs"] else None

            def bat_sr(g):
                return round(g["runs"] / g["balls"] * 100, 1) if g["balls"] else 0

            top_runs = sorted(bat_tot.values(),
                              key=lambda g: (g["runs"], g["sixes"]),
                              reverse=True)[:10]

            def bowl_avg(g):
                return round(g["runs"] / g["wkts"], 1) if g["wkts"] else None

            def bowl_econ(g):
                return round(g["runs"] / (g["balls"] / 6), 2) if g["balls"] else 0

            top_wkts = sorted(bowl_tot.values(),
                              key=lambda g: (g["wkts"], -g["runs"]),
                              reverse=True)[:10]

            editions.append({
                **ed,
                "matches": matches,
                "knockouts": knockouts,
                "groups": groups,
                "final_raw": final_raw,
                "final": final_m,
                "champion": champion,
                "runner": runner,
                "n_matches": len(matches),
                "top_runs": [
                    {"pid": g["pid"], "name": g["name"], "runs": g["runs"],
                     "inns": g["inns"], "avg": bat_avg(g), "sr": bat_sr(g),
                     "hs": g["hs"], "hs_no": g["hs_no"]}
                    for g in top_runs],
                "top_wkts": [
                    {"pid": g["pid"], "name": g["name"], "wkts": g["wkts"],
                     "inns": g["inns"], "avg": bowl_avg(g), "econ": bowl_econ(g),
                     "best": (f"{g['best_w']}/{g['best_r']}"
                              if g["best_w"] >= 0 else "—")}
                    for g in top_wkts],
            })
        out.append({**t, "editions": editions})
    return out
