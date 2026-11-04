"""Words a search leaves out, by language: they stand in almost every document and in the
questions people ask ("Wie viel Hundesteuer zahle ich?"), so they decide nothing and, without
the list, push the words that do decide out of a long query.

German: the stop word list of the Snowball project (https://snowballstem.org/algorithms/german/
stop.txt, licence at the end of this file), and "dass" beside "daß" and the forms of "unser"
beside the list's "unse", "unsem", "unsen" and "unses". Other languages have none yet: the
search was measured on German only (`lekto evaluate-search`).
"""

from collections.abc import Collection

_GERMAN = """
    aber alle allem allen aller alles als also am an ander andere anderem anderen anderer
    anderes anderm andern anderr anders auch auf aus bei bin bis bist da damit dann der den des
    dem die das daß dass derselbe derselben denselben desselben demselben dieselbe dieselben
    dasselbe dazu dein deine deinem deinen deiner deines denn derer dessen dich dir du dies
    diese diesem diesen dieser dieses doch dort durch ein eine einem einen einer eines einig
    einige einigem einigen einiger einiges einmal er ihn ihm es etwas euer eure eurem euren
    eurer eures für gegen gewesen hab habe haben hat hatte hatten hier hin hinter ich mich mir
    ihr ihre ihrem ihren ihrer ihres euch im in indem ins ist jede jedem jeden jeder jedes jene
    jenem jenen jener jenes jetzt kann kein keine keinem keinen keiner keines können könnte
    machen man manche manchem manchen mancher manches mein meine meinem meinen meiner meines mit
    muss musste nach nicht nichts noch nun nur ob oder ohne sehr sein seine seinem seinen seiner
    seines selbst sich sie ihnen sind so solche solchem solchen solcher solches soll sollte
    sondern sonst über um und uns unse unsem unsen unser unses unsere unserem unseren unseres
    unter viel vom von vor während war waren warst was weg weil weiter welche welchem welchen
    welcher welches wenn werde werden wie wieder will wir wird wirst wo wollen wollte würde
    würden zu zum zur zwar zwischen
"""
GERMAN = frozenset(_GERMAN.split())
BY_LOCALE = {"deu": GERMAN}


def stop_words(locales: Collection[str]) -> list[str]:
    """The stop words of the languages, sorted (as Meilisearch keeps them)."""
    return sorted(set().union(*(BY_LOCALE.get(locale, frozenset()) for locale in locales)))


# The Snowball stop word list is distributed under this licence:
#
# Copyright (c) 2001, Dr Martin Porter,
# Copyright (c) 2002, Richard Boulton.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of
#    conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
#    conditions and the following disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to
#    endorse or promote products derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
